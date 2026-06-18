"""Explanation engine (spec §5.6; Part 4.2; roadmap §6.5-6.13).

Assembles per-section context bundles, makes the SINGLE constrained Anthropic
call, validates each section (tolerant number check + cause check), retries once,
then falls back to a flat templated line per failing section. The brief NEVER
blocks on the model (spec §5.6 failure fallback).

The Anthropic call is isolated in _call_model and injectable, so the whole
orchestration — bundling, validation, retry, fallback, runs/ dump — is testable
offline with a fake model.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from engine.matcher import Article, ScoredArticle, check_cause, match_section
from engine.primers import PRIMERS
from engine.validator import validate_prose

SYSTEM_PROMPT = (
    "You are the writer for a daily market brief. You are given computed numbers "
    "and a small set of news articles. Your ONLY job is to write the causal "
    "explanation — the 'why' — for each section. The numbers are written separately "
    "by the system, NOT by you. You operate under three hard rules:\n\n"
    "1. Write NO NUMBERS AT ALL in your 'cause' text. No prices, no percentages, no "
    "basis points, no dollar figures, no levels. Not even approximate ones. The "
    "system already states every figure; your job is the reason behind the move in "
    "words only. Write \"oil fell sharply\" or \"yields eased\", never \"oil fell "
    "1.3%\" or \"yields eased to 4.43%\". A single number in your cause text causes "
    "the whole section to be discarded.\n"
    "2. Every causal claim (\"X fell because Y\", \"on soft demand\", \"after the "
    "data\") must reference one of the supplied articles by its source_id. If no "
    "supplied article supports a cause, set cause to \"no clear catalyst\" and "
    "confidence low. Inventing a plausible cause is a failure; honest uncertainty "
    "is correct.\n"
    "3. First EXTRACT the explicit causal claims reporters made, THEN write the "
    "cause using only those extracted reasons. Keep it to one or two plain "
    "declarative sentences. No em dashes, no emojis.\n\n"
    "Output strict JSON only, no prose outside the JSON. The TOP-LEVEL object is "
    "keyed BY SECTION ID (e.g. {\"us_equities\": {...}, \"commodities\": {...}}); each "
    "value is {\"cause\": string, \"cause_source_id\": string or null, \"confidence\": "
    "\"low|medium|high\"}. Do NOT wrap the sections in a \"per_section\" key."
)

# The model writes ONLY the number-free cause + its source tag + confidence; the
# system writes every figure (spec §1). Keep the schema minimal so the model is not
# tempted to restate numbers (the level/change/prose fields are gone).
OUTPUT_SCHEMA = {
    "<section_id>": {
        "cause": "string (the why, NO numbers)",
        "cause_source_id": "string or null",
        "confidence": "low|medium|high",
    }
}

# A model caller takes (system, user_json, model) and returns the raw JSON string.
ModelCaller = Callable[[str, str, str], str]


@dataclass
class SectionBundle:
    section_id: str
    numbers: dict[str, float]
    primer: str
    articles: list[ScoredArticle] = field(default_factory=list)


@dataclass
class SectionResult:
    section_id: str
    prose: str
    cause_source_id: Optional[str]
    confidence: str
    templated: bool = False          # True when the model output was rejected -> fallback
    # The matched article(s) behind the causal "why", resolved from cause_source_id
    # to {title, url}, so the template can render a clickable citation (spec §7).
    # Empty when the section made no cause claim (quiet tape, honest one-liner).
    cited_sources: tuple[dict, ...] = ()


# --------------------------------------------------------------------------- #
# Bundle assembly
# --------------------------------------------------------------------------- #
def build_bundles(
    section_numbers: dict[str, dict[str, float]],
    articles: list[Article],
    *,
    watchlist_tickers: Optional[list[str]] = None,
) -> list[SectionBundle]:
    """One bundle per section: its numbers, scored articles, and primer."""
    bundles: list[SectionBundle] = []
    for section_id, numbers in section_numbers.items():
        extra = watchlist_tickers if section_id == "watchlist" else None
        scored = match_section(section_id, articles, extra_keywords=extra)
        bundles.append(SectionBundle(
            section_id=section_id,
            numbers=numbers,
            primer=PRIMERS.get(section_id, ""),
            articles=scored,
        ))
    return bundles


# Per-stock pseudo-sections are keyed "stock:<TICKER>" so they fold into the same
# single model call as the real sections without colliding with a section id.
STOCK_SECTION_PREFIX = "stock:"

_STOCK_PRIMER = (
    "This is a single company. Write a one-line, number-free reason for its move "
    "drawn ONLY from the supplied articles about this company. If none of the "
    "articles explain it, set cause to \"no clear catalyst\" and confidence low. "
    "Do not generalize from the broad market."
)


def build_stock_bundles(
    tickers: list[str],
    articles: list[Article],
    *,
    company_names: Optional[dict[str, str]] = None,
) -> list[SectionBundle]:
    """One bundle per surfaced ticker, keyed 'stock:<TICKER>'.

    Articles are matched on the ticker symbol plus the company name (when known),
    so a per-stock cause is grounded in reporting about that company. Numbers are
    empty: the model writes a number-free cause and the system writes every figure
    (the per-stock stat table), so a stock cause carrying any number is rejected.
    """
    company_names = company_names or {}
    bundles: list[SectionBundle] = []
    for ticker in tickers:
        keywords = [ticker]
        name = company_names.get(ticker)
        if name:
            keywords.append(name)
        section_id = f"{STOCK_SECTION_PREFIX}{ticker}"
        scored = match_section(section_id, articles, extra_keywords=keywords)
        bundles.append(SectionBundle(
            section_id=section_id,
            numbers={},
            primer=_STOCK_PRIMER,
            articles=scored,
        ))
    return bundles


def _user_message(bundles: list[SectionBundle]) -> str:
    sections = []
    for b in bundles:
        sections.append({
            "section_id": b.section_id,
            "numbers": b.numbers,
            "primer": b.primer,
            "articles": [
                {"source_id": s.article.source_id, "title": s.article.title,
                 "summary": s.article.summary, "url": s.article.url,
                 "match_score": round(s.match_score, 2)}
                for s in b.articles
            ],
        })
    return json.dumps({"sections": sections, "output_schema": OUTPUT_SCHEMA})


# --------------------------------------------------------------------------- #
# The model call (isolated, injectable)
# --------------------------------------------------------------------------- #
def _extract_json(text: str) -> str:
    """Return the JSON object embedded in a model reply.

    The system prompt asks for strict JSON, but models routinely wrap it in a
    ```json fence or add a one-line preamble. json.loads on that raises and the
    whole call silently degrades to templates (the failure we hit on the first
    real sends). Strip a fenced block if present, else fall back to the span
    from the first '{' to the last '}'. Returns the input unchanged if neither
    applies, so a clean reply is untouched and json.loads still does the real
    validation downstream.
    """
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _call_model(system: str, user_json: str, model: str) -> str:
    """Real Anthropic call (anthropic==0.109.2). Imported lazily."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user_json}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return _extract_json(text)


# --------------------------------------------------------------------------- #
# Orchestration: call -> validate -> retry once -> template
# --------------------------------------------------------------------------- #
def generate(
    bundles: list[SectionBundle],
    *,
    model: str,
    tolerance_pct: float,
    caller: Optional[ModelCaller] = None,
    templated_fallback: Callable[[str], str],
) -> tuple[dict[str, SectionResult], bool, Optional[dict]]:
    """Run the explanation engine. Returns (results, degraded, raw_json_for_runs).

    degraded is True if the whole call failed or any section fell back to a
    template. Never raises; the brief ships regardless (spec §5.6).
    """
    call = caller or _call_model
    inputs_by_section = {b.section_id: list(b.numbers.values()) for b in bundles}
    valid_source_ids = {
        b.section_id: {s.article.source_id for s in b.articles} for b in bundles
    }

    raw = _try_call(call, bundles, model)
    if raw is None:
        # Whole call failed -> template every section (degraded).
        results = {b.section_id: _templated_result(b.section_id, templated_fallback)
                   for b in bundles}
        return results, True, None

    parsed = raw
    results: dict[str, SectionResult] = {}
    degraded = False
    retried_once = False

    for b in bundles:
        entry = parsed.get(b.section_id)
        ok, result = _accept_section(
            b.section_id, entry, inputs_by_section[b.section_id],
            valid_source_ids[b.section_id], tolerance_pct, b.articles,
        )
        if not ok and not retried_once:
            # Retry the whole call once (Part 4.4 step 5 / §6.9).
            retried_once = True
            raw2 = _try_call(call, bundles, model)
            if raw2 is not None:
                parsed = raw2
                entry = parsed.get(b.section_id)
                ok, result = _accept_section(
                    b.section_id, entry, inputs_by_section[b.section_id],
                    valid_source_ids[b.section_id], tolerance_pct, b.articles,
                )
        if not ok:
            result = _templated_result(b.section_id, templated_fallback)
            degraded = True
        results[b.section_id] = result

    return results, degraded, parsed


# The output schema in the prompt is shaped {"per_section": {<entry fields>}}, and
# models routinely echo that literal wrapper: they return {"per_section": {section_id:
# entry, ...}} instead of {section_id: entry, ...}. We expect the latter, so an
# un-normalized reply keys to None for every section and the whole brief silently
# degrades to templates (the failure behind the 2026-06-18 send). Peel a known
# envelope key so a wrapped reply is accepted exactly like a flat one.
_ENVELOPE_KEYS = ("per_section", "sections", "output")


def _unwrap_sections(data: dict) -> dict:
    """Peel a per_section/sections envelope so entries key by section id.

    Only unwraps when the sole top-level key is a known envelope wrapping a dict;
    a reply already keyed by section id is returned unchanged.
    """
    for key in _ENVELOPE_KEYS:
        inner = data.get(key)
        if isinstance(inner, dict) and len(data) == 1:
            return inner
    return data


def _try_call(call: ModelCaller, bundles: list[SectionBundle], model: str) -> Optional[dict]:
    try:
        raw = call(SYSTEM_PROMPT, _user_message(bundles), model)
        data = json.loads(raw)
        return _unwrap_sections(data) if isinstance(data, dict) else None
    except Exception as exc:
        # Never raise (the brief ships regardless, spec §5.6), but DO surface the
        # cause: a silently degrading model is the failure mode the spec warns is
        # hardest to notice (§13). One line to the Actions log, classified.
        print(f"  narrative: model call failed [{type(exc).__name__}]: {exc}")
        return None


def _accept_section(
    section_id: str,
    entry: Optional[dict],
    inputs: list[float],
    valid_source_ids: set[str],
    tolerance_pct: float,
    articles: Optional[list["ScoredArticle"]] = None,
) -> tuple[bool, Optional[SectionResult]]:
    """Validate one section's CAUSE: number-free + cause-tagged (Part 4.4 / 4.5).

    The model now writes only the number-free 'why'; the system writes every
    figure. So the gate is: the cause carries NO unsupported number (in practice
    no number at all — the inputs are not in the cause), and every causal claim is
    tagged to a supplied article. This makes wrong stats impossible by construction
    (spec §1): the model literally cannot emit a number into the rendered brief.
    """
    if not isinstance(entry, dict):
        return False, None
    cause = entry.get("cause", "")
    if not isinstance(cause, str) or not cause.strip():
        return False, None

    # The cause must be number-free. Any numeric token not consistent with the
    # input set is invented; since causes should carry no figures at all, this
    # rejects a cause that slipped a number in (e.g. a stray "$4 per gallon").
    number_check = validate_prose(cause, inputs, tolerance_pct=tolerance_pct)
    if not number_check.ok:
        return False, None

    cause_source_id = entry.get("cause_source_id")
    cause_check = check_cause(cause, cause_source_id)
    if not cause_check.ok:
        return False, None
    # A tagged source_id must actually be one we supplied (not invented).
    if cause_source_id and cause_source_id not in valid_source_ids:
        return False, None

    return True, SectionResult(
        section_id=section_id,
        prose=cause.strip(),   # the rendered section = computed numbers + this cause
        cause_source_id=cause_source_id,
        confidence=str(entry.get("confidence", "low")),
        templated=False,
        cited_sources=_resolve_cited(cause_source_id, articles),
    )


def _resolve_cited(
    cause_source_id: Optional[str], articles: Optional[list["ScoredArticle"]],
) -> tuple[dict, ...]:
    """Map a validated cause_source_id to the matched article's {title, url}.

    The source_id is already proven to be one we supplied (validated above), so
    this only renders a citation the reader can click (spec §7). Returns empty when
    the section made no cause claim, so the template shows no empty "Source" label.
    """
    if not cause_source_id or not articles:
        return ()
    for s in articles:
        if s.article.source_id == cause_source_id:
            url = s.article.url or ""
            if not url:
                return ()
            return ({"title": s.article.title, "url": url},)
    return ()


def _templated_result(section_id: str, templated_fallback: Callable[[str], str]) -> SectionResult:
    return SectionResult(
        section_id=section_id,
        prose=templated_fallback(section_id),
        cause_source_id=None,
        confidence="low",
        templated=True,
    )


# --------------------------------------------------------------------------- #
# runs/ dump (Part 4 / §6.11)
# --------------------------------------------------------------------------- #
def dump_run(
    results: dict[str, SectionResult],
    raw_json: Optional[dict],
    *,
    runs_dir: str,
    date_str: str,
) -> str:
    """Write the structured JSON for read-by-eye auditing (spec §5.6, §8)."""
    os.makedirs(runs_dir, exist_ok=True)
    path = os.path.join(runs_dir, f"{date_str}.json")
    payload = {
        "date": date_str,
        "sections": {k: asdict(v) for k, v in results.items()},
        "raw_model_output": raw_json,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path
