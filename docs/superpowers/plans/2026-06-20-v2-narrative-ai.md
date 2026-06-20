# Narrative / AI Layer Implementation Plan (Sub-Project 3 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the v2 engine's resolved numbers and fetched articles into validated, source-tagged "why" prose — a deterministic article matcher, one constrained Claude (Sonnet 4.6) narration call, and a cheap-model (Haiku 4.5) entailment validator appended to the existing validator chain.

**Architecture:** Two pure stages (compute same-day numbers, match articles to sections) feed one injectable model call (narrate) whose output runs through the existing worst-verdict-wins validator chain, now with three validators: the ported tag-only check, the ported tolerant number check, and a NEW entailment check. The model never introduces a number; "no clear catalyst" is an encouraged output; the brief degrades to templated lines and never blocks on the model or news.

**Tech Stack:** Python 3.12, Pydantic v2, the `anthropic` SDK (structured outputs via `messages.parse()` on `claude-sonnet-4-6` / `claude-haiku-4-5`), pytest. uv-managed venv at `v2/.venv`.

## Global Constraints

- Run tests with `cd v2 && ./.venv/bin/python -m pytest`. Bash cwd does NOT persist between calls — `cd /Users/jakeliess/market-brief/v2` each call.
- Run git from the REPO ROOT (`/Users/jakeliess/market-brief`) using `v2/` paths.
- venv is uv-managed (NO pip). Add deps with `uv pip install --python .venv/bin/python <pkg>` AND add to `v2/pyproject.toml`.
- Branch `build/v2`, mirrors to origin; NOT main; no auto-PR. Push after each task.
- The model NEVER invents or alters a number. Numbers come only from `ComputedNumbers`.
- Every causal claim traces to a supplied article (`cause_source_id`) or is hedged/stripped. "No clear catalyst" is a correct, encouraged output.
- Professional tone in any copy: no em dashes, no emojis, plain declarative prose.
- The brief never blocks on the model or news; it degrades to templated lines.
- Tests NEVER hit the live Anthropic API. The narrator and entailment validator take an injectable client; tests use a fake. `MARKET_BRIEF_OFFLINE=1` ⇒ templated path, no client constructed.
- Do NOT touch the v1 app (root `brief.py`, `engine/`, `render/`, `sources/`).

---

## File Structure

| File | Responsibility |
|---|---|
| `v2/marketbrief/match/keywords.py` | Ported `SECTION_KEYWORDS` + shared causal regex (single source of truth) |
| `v2/marketbrief/match/scorer.py` | Ported `score_article` / `match_section` → `ScoredArticle`; `match_sections` map builder |
| `v2/marketbrief/compute/derive.py` | PURE: `resolved_fields` → `ComputedNumbers` (same-day figures only) |
| `v2/marketbrief/narrate/number_check.py` | Ported tolerant number check, wrapped as a `NumberCheck` Validator |
| `v2/marketbrief/narrate/client.py` | Thin Anthropic client wrapper + offline seam + protocol the fake satisfies |
| `v2/marketbrief/narrate/prompt.py` | System prompt + per-section bundle assembly (spec §5.6 rubric) |
| `v2/marketbrief/narrate/templated.py` | Deterministic fallback `NarratedWhy` lines (degrade path) |
| `v2/marketbrief/narrate/narrator.py` | Builds prompt, ONE Sonnet call, parses structured output → `dict[section_id, NarratedWhy]` |
| `v2/marketbrief/narrate/entailment.py` | NEW `EntailmentCheck` Validator (Haiku, injectable client) |
| `v2/marketbrief/narrate/chain.py` | EXISTS — import shared causal regex from `keywords.py` (de-dupe) |
| `v2/marketbrief/core/pipeline.py` | EXISTS — replace `compute/match/narrate` stubs with real stages |
| `v2/marketbrief/core/config.py` | EXISTS — add `NarrateConfig` (model IDs) to `Config` |
| `v2/config.yaml` | EXISTS — add `narrate:` block |

**Build order:** G1 = Tasks 1-3 (pure, no model). G2 = Tasks 4-7 (client seam, number check, narrator, templated). G3 = Tasks 8-9 (entailment + pipeline wire-up).

---

## Task 1: Shared keywords + ported article scorer

**Files:**
- Create: `v2/marketbrief/match/__init__.py` (empty)
- Create: `v2/marketbrief/match/keywords.py`
- Create: `v2/marketbrief/match/scorer.py`
- Modify: `v2/marketbrief/narrate/chain.py` (import the shared regex)
- Test: `v2/tests/test_scorer.py`

**Interfaces:**
- Consumes: `marketbrief.core.models.Article` (`source_id, title, summary, url`).
- Produces: `match.keywords.SECTION_KEYWORDS: dict[str, list[str]]`, `match.keywords.CAUSAL_RE` (compiled). `match.scorer.ScoredArticle` (frozen dataclass: `article: Article`, `match_score: float`). `score_article(article: Article, keywords: list[str]) -> float`. `match_section(section_id: str, articles: list[Article], *, extra_keywords: list[str] | None = None) -> list[ScoredArticle]`. Constants `MATCH_SCORE_THRESHOLD = 0.15`, `TOP_ARTICLES = 3`.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_scorer.py`:

```python
from marketbrief.core.models import Article
from marketbrief.match.scorer import (
    score_article, match_section, ScoredArticle, MATCH_SCORE_THRESHOLD, TOP_ARTICLES,
)
from marketbrief.match.keywords import SECTION_KEYWORDS, CAUSAL_RE


def _a(title, summary=""):
    return Article(source_id="x-1", title=title, summary=summary)


def test_title_hits_weighted_double_over_summary():
    kw = ["oil", "opec"]
    title_only = score_article(_a("Oil jumps", ""), kw)      # 1 title hit -> 2/2
    summary_only = score_article(_a("Markets", "oil up"), kw) # 1 summary hit -> 1/2
    assert title_only == 1.0
    assert summary_only == 0.5


def test_empty_keywords_scores_zero():
    assert score_article(_a("anything"), []) == 0.0


def test_match_section_returns_top_n_sorted_desc():
    arts = [
        _a("Oil and crude and opec and wti", "barrel brent"),  # high
        _a("Oil edges up", ""),                                 # mid
        _a("Quiet markets", ""),                                # zero -> dropped
    ]
    out = match_section("commodities", arts)
    assert all(isinstance(s, ScoredArticle) for s in out)
    assert len(out) <= TOP_ARTICLES
    assert out[0].match_score >= out[-1].match_score
    assert all(s.article.title != "Quiet markets" for s in out)


def test_below_threshold_best_returns_empty():
    # one weak summary hit across a long keyword list -> below 0.15
    arts = [_a("Totally unrelated headline", "mentions oil once")]
    out = match_section("commodities", arts)
    assert out == []


def test_keyword_table_and_regex_present():
    assert "us_equities" in SECTION_KEYWORDS
    assert CAUSAL_RE.search("yields fell on soft demand")
    assert not CAUSAL_RE.search("yields were unchanged today")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_scorer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'marketbrief.match'`

- [ ] **Step 3: Write keywords + scorer**

`v2/marketbrief/match/__init__.py`: empty file.

`v2/marketbrief/match/keywords.py` (ported verbatim from v1 `engine/matcher.py`):

```python
"""Per-section keyword/ticker tables and the causal-verb regex (ported from v1
engine/matcher.py). Single source of truth: chain.py imports CAUSAL_RE from here."""
from __future__ import annotations
import re

SECTION_KEYWORDS: dict[str, list[str]] = {
    "us_equities": ["s&p", "nasdaq", "dow", "russell", "stocks", "equities",
                    "index", "rally", "selloff", "wall street", "shares"],
    "rates_and_dollar": ["yield", "treasury", "10-year", "2-year", "fed", "auction",
                          "dgs10", "rate", "dollar", "dxy", "basis points", "bps"],
    "commodities": ["oil", "crude", "wti", "opec", "gold", "barrel", "brent",
                    "energy", "bullion"],
    "washington": ["fed", "fomc", "powell", "tariff", "shutdown", "fiscal",
                   "congress", "white house", "trump", "regulation", "treasury dept"],
    "movers": ["surged", "plunged", "jumped", "tumbled", "earnings", "guidance",
               "upgrade", "downgrade", "shares"],
    "economic_data_scorecard": ["cpi", "inflation", "payrolls", "jobs", "gdp",
                                 "pce", "retail sales", "ism", "consumer", "data"],
    "earnings_on_deck": ["earnings", "reports", "quarterly", "results", "eps",
                         "guidance", "pre-open", "after close"],
    "watchlist": [],   # populated from config tickers at match time
    "crypto": ["bitcoin", "ethereum", "btc", "eth", "crypto", "token", "coin"],
    "volatility_breadth": ["vix", "volatility", "hedging", "fear", "breadth",
                           "advancers", "decliners"],
    "what_to_watch_today": ["today", "schedule", "due", "expected", "calendar"],
}

# Causal verbs/phrases that REQUIRE a cause_source_id (spec §5.6 / Part 4.5).
CAUSAL_RE = re.compile(
    r"\b(because|due to|on (?:soft|strong|weak|robust|the)|amid|after|as|driven by|"
    r"thanks to|owing to|spurred by|fueled by|on the back of)\b",
    re.IGNORECASE,
)
```

`v2/marketbrief/match/scorer.py` (ported verbatim, typed against the v2 `Article`):

```python
"""Deterministic article->section scorer (ported from v1 engine/matcher.py).

No model. Scores each candidate article by title (weight 2) + summary overlap and
attaches the top 2-3 with their numeric match_score so a weak match is visible.
An empty result pushes the model toward 'no clear catalyst' (spec §4.3, §5.6)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from marketbrief.core.models import Article
from marketbrief.match.keywords import SECTION_KEYWORDS

MATCH_SCORE_THRESHOLD = 0.15   # below this, attach no articles
TOP_ARTICLES = 3


@dataclass(frozen=True)
class ScoredArticle:
    article: Article
    match_score: float


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9&\-]+", text.lower()))


def score_article(article: Article, keywords: list[str]) -> float:
    """score = (title_hits*2 + summary_hits) / len(keywords). Title weighted 2x."""
    if not keywords:
        return 0.0
    kw = [k.lower() for k in keywords]
    title_hits = sum(1 for k in kw if k in article.title.lower())
    summary_hits = sum(1 for k in kw if k in article.summary.lower())
    return (title_hits * 2 + summary_hits) / len(kw)


def match_section(
    section_id: str,
    articles: list[Article],
    *,
    extra_keywords: list[str] | None = None,
) -> list[ScoredArticle]:
    """Top 2-3 scored articles for a section; empty if best score below threshold."""
    keywords = list(SECTION_KEYWORDS.get(section_id, [])) + list(extra_keywords or [])
    scored = [ScoredArticle(a, score_article(a, keywords)) for a in articles]
    scored = [s for s in scored if s.match_score > 0]
    scored.sort(key=lambda s: s.match_score, reverse=True)
    top = scored[:TOP_ARTICLES]
    if not top or top[0].match_score < MATCH_SCORE_THRESHOLD:
        return []
    return top
```

- [ ] **Step 4: De-dupe the causal regex in chain.py**

In `v2/marketbrief/narrate/chain.py`, delete the local `_CAUSAL_RE = re.compile(...)` block and the now-unused `import re`, and import the shared one. Change the top of the file to:

```python
from __future__ import annotations
from marketbrief.core.models import Cause
from marketbrief.core.enums import Verdict
from marketbrief.core.context import BriefContext
from marketbrief.core.protocols import Validator
from marketbrief.core.isolation import run_isolated
from marketbrief.match.keywords import CAUSAL_RE
```

Then in `TagOnlyCauseCheck.judge`, change `_CAUSAL_RE.search(cause.claim)` to `CAUSAL_RE.search(cause.claim)`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_scorer.py tests/test_chain.py -q`
Expected: PASS (the existing chain test still passes with the shared regex).

- [ ] **Step 6: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/match/ v2/marketbrief/narrate/chain.py v2/tests/test_scorer.py
git commit -m "feat(v2): port article scorer + shared causal regex"
git push origin build/v2
```

---

## Task 2: Same-day compute stage

**Files:**
- Create: `v2/marketbrief/compute/__init__.py` (empty)
- Create: `v2/marketbrief/compute/derive.py`
- Test: `v2/tests/test_derive.py`

**Interfaces:**
- Consumes: `ctx.resolved_fields: dict[str, Field]` (Field has `metric, value, source, stale`; `is_usable` = not missing and not stale), `Config`.
- Produces: `derive_numbers(resolved_fields: dict[str, Field], config: Config) -> ComputedNumbers`. `ComputedNumbers(values: dict[str, float], diff_lines: list[str])` already exists in `core/models.py`. Keys put in `values`: each usable field's own value under `f"{metric}"`; the same-day `2s10s` spread under `"spread_2s10s"` when both `dgs10`/`us10y` and `us2y`/`dgs2` are present (key names match resolver output — use whatever the resolver emits for the 10y and 2y; the resolver field keys are the metric names from the symbol table).

> NOTE for the implementer: confirm the exact resolved 10y / 2y metric keys by reading `v2/marketbrief/fetch/resolver.py` and `v2/marketbrief/core/symbols.py` before writing Step 3. The test below uses placeholder keys `us10y` / `us2y`; adjust both the test and the implementation to the real keys if they differ. Do not invent a key the resolver never emits.

- [ ] **Step 1: Confirm the real metric keys**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -c "from marketbrief.core.symbols import *; import marketbrief.core.symbols as s; print([n for n in dir(s) if not n.startswith('_')])"`
Then read `v2/marketbrief/core/symbols.py` to find the 10-year and 2-year metric names. Use those names in Steps 2-3 wherever this plan writes `us10y` / `us2y`.

- [ ] **Step 2: Write the failing test** — `v2/tests/test_derive.py` (replace `us10y`/`us2y` with the real keys from Step 1):

```python
from marketbrief.core.config import Config
from marketbrief.core.models import Field, ComputedNumbers
from marketbrief.compute.derive import derive_numbers

CFG = Config()


def _f(metric, value, *, source="yfinance", stale=False):
    return Field(metric=metric, value=value, source=source, stale=stale)


def test_usable_values_included():
    resolved = {"us10y": _f("us10y", 4.25), "wti": _f("wti", 76.1)}
    out = derive_numbers(resolved, CFG)
    assert isinstance(out, ComputedNumbers)
    assert out.values["us10y"] == 4.25
    assert out.values["wti"] == 76.1


def test_missing_or_stale_field_excluded():
    resolved = {
        "us10y": _f("us10y", None, source="missing"),
        "wti": _f("wti", 76.1, stale=True),
    }
    out = derive_numbers(resolved, CFG)
    assert "us10y" not in out.values
    assert "wti" not in out.values


def test_2s10s_spread_when_both_legs_present():
    resolved = {"us10y": _f("us10y", 4.25), "us2y": _f("us2y", 3.85)}
    out = derive_numbers(resolved, CFG)
    assert round(out.values["spread_2s10s"], 2) == 0.40


def test_2s10s_absent_when_a_leg_missing():
    resolved = {"us10y": _f("us10y", 4.25)}
    out = derive_numbers(resolved, CFG)
    assert "spread_2s10s" not in out.values


def test_history_derived_figures_absent():
    # No rolling history in #3: nothing like *_5d_high / *_streak appears.
    resolved = {"us10y": _f("us10y", 4.25)}
    out = derive_numbers(resolved, CFG)
    assert not any("_5d" in k or "_20d" in k or "streak" in k for k in out.values)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_derive.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'marketbrief.compute'`

- [ ] **Step 4: Write the implementation**

`v2/marketbrief/compute/__init__.py`: empty.

`v2/marketbrief/compute/derive.py` (replace `TEN_YEAR` / `TWO_YEAR` constants with the real keys from Step 1):

```python
"""Same-day compute stage (PURE, no I/O, no model).

Builds the ComputedNumbers input set the number-validator checks against and the
narrator may cite. Computes ONLY figures available from today's resolved fields:
each usable field's value, plus same-day spreads (2s10s). Rolling-history figures
(5/20-day high/low, streaks, weekly sums, z-scores, 'yesterday') are deliberately
NOT computed here; they belong to the later compute sub-project."""
from __future__ import annotations
from marketbrief.core.config import Config
from marketbrief.core.models import Field, ComputedNumbers

TEN_YEAR = "us10y"   # TODO: replace with the real resolver metric key (Step 1)
TWO_YEAR = "us2y"    # TODO: replace with the real resolver metric key (Step 1)


def derive_numbers(resolved_fields: dict[str, Field], config: Config) -> ComputedNumbers:
    values: dict[str, float] = {}
    for metric, field in resolved_fields.items():
        if field.is_usable and field.value is not None:
            values[metric] = field.value

    ten = resolved_fields.get(TEN_YEAR)
    two = resolved_fields.get(TWO_YEAR)
    if ten and two and ten.is_usable and two.is_usable \
            and ten.value is not None and two.value is not None:
        values["spread_2s10s"] = ten.value - two.value

    return ComputedNumbers(values=values, diff_lines=[])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_derive.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/compute/ v2/tests/test_derive.py
git commit -m "feat(v2): same-day compute stage (history deferred)"
git push origin build/v2
```

---

## Task 3: match_sections map builder (GATE 1 close)

**Files:**
- Modify: `v2/marketbrief/match/scorer.py` (add `match_sections`)
- Test: `v2/tests/test_scorer.py` (append)

**Interfaces:**
- Consumes: `ctx.articles: list[Article]`, `Config.watchlist: list[str]`, `SECTION_KEYWORDS`.
- Produces: `match_sections(articles: list[Article], config: Config) -> dict[str, list[ScoredArticle]]` — one entry per section in `SECTION_KEYWORDS`; watchlist tickers from `config.watchlist` are passed as `extra_keywords` to the `watchlist` section.

- [ ] **Step 1: Write the failing test** — append to `v2/tests/test_scorer.py`:

```python
from marketbrief.match.scorer import match_sections
from marketbrief.core.config import Config


def test_match_sections_covers_every_section():
    arts = [_a("Oil and crude and opec spike", "barrel brent energy")]
    out = match_sections(arts, Config())
    assert set(out.keys()) == set(SECTION_KEYWORDS.keys())
    assert any(out["commodities"])  # the oil article landed in commodities


def test_watchlist_uses_config_tickers():
    arts = [_a("NVDA NVDA NVDA surges on guidance", "nvda")]
    out = match_sections(arts, Config(watchlist=["nvda"]))
    assert any(out["watchlist"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_scorer.py::test_match_sections_covers_every_section -q`
Expected: FAIL — `ImportError: cannot import name 'match_sections'`

- [ ] **Step 3: Add `match_sections`** — append to `v2/marketbrief/match/scorer.py`:

```python
def match_sections(articles, config) -> dict[str, list[ScoredArticle]]:
    """Run match_section for every known section; watchlist gets config tickers."""
    out: dict[str, list[ScoredArticle]] = {}
    for section_id in SECTION_KEYWORDS:
        extra = list(config.watchlist) if section_id == "watchlist" else None
        out[section_id] = match_section(section_id, articles, extra_keywords=extra)
    return out
```

- [ ] **Step 4: Run the full suite (GATE 1 verification)**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest -q`
Expected: PASS (all prior 84 tests plus the new scorer/derive tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/match/scorer.py v2/tests/test_scorer.py
git commit -m "feat(v2): match_sections map builder (gate 1: pure matcher+compute)"
git push origin build/v2
```

**GATE 1 COMPLETE** — pure matcher + compute, no model. Stop for sign-off.

---

## Task 4: Add anthropic dep + NarrateConfig + client seam

**Files:**
- Modify: `v2/pyproject.toml` (add `anthropic`)
- Modify: `v2/marketbrief/core/config.py` (add `NarrateConfig`)
- Modify: `v2/config.yaml` (add `narrate:` block)
- Create: `v2/marketbrief/narrate/client.py`
- Test: `v2/tests/test_narrate_client.py`, `v2/tests/test_config.py` (append)

**Interfaces:**
- Consumes: `marketbrief.fetch.net.is_offline`.
- Produces: `NarrateConfig(model: str = "claude-sonnet-4-6", entailment_model: str = "claude-haiku-4-5", max_tokens: int = 1500)` added to `Config` as `narrate`. `client.NarrationClient` Protocol with `parse(model: str, system: str, user: str, schema: dict, max_tokens: int) -> dict`. `client.build_client() -> NarrationClient | None` (returns `None` when offline or the SDK / key is unavailable). `client.AnthropicClient` (real wrapper).

- [ ] **Step 1: Add the dependency**

Run:
```bash
cd /Users/jakeliess/market-brief/v2 && uv pip install --python .venv/bin/python anthropic
```
Then add `"anthropic>=0.69"` to the `dependencies` list in `v2/pyproject.toml` (match the installed major; read the installed version with `./.venv/bin/python -c "import anthropic; print(anthropic.__version__)"` and pin the floor to that).

- [ ] **Step 2: Write the failing test** — `v2/tests/test_narrate_client.py`:

```python
import os
from marketbrief.narrate.client import build_client


def test_build_client_returns_none_when_offline(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    assert build_client() is None


def test_build_client_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert build_client() is None
```

Append to `v2/tests/test_config.py`:

```python
def test_narrate_config_defaults():
    from marketbrief.core.config import Config
    cfg = Config()
    assert cfg.narrate.model == "claude-sonnet-4-6"
    assert cfg.narrate.entailment_model == "claude-haiku-4-5"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_narrate_client.py tests/test_config.py::test_narrate_config_defaults -q`
Expected: FAIL — module / attribute missing.

- [ ] **Step 4: Add NarrateConfig**

In `v2/marketbrief/core/config.py`, add the model and wire it into `Config`:

```python
class NarrateConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    entailment_model: str = "claude-haiku-4-5"
    max_tokens: int = 1500


class Config(BaseModel):
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    watchlist: list[str] = Field(default_factory=list)
    narrate: NarrateConfig = Field(default_factory=NarrateConfig)
```

Add to `v2/config.yaml` (top level):

```yaml
narrate:
  model: "claude-sonnet-4-6"
  entailment_model: "claude-haiku-4-5"
  max_tokens: 1500
```

- [ ] **Step 5: Write the client seam** — `v2/marketbrief/narrate/client.py`:

```python
"""Anthropic client seam: the only place the SDK is touched.

The narrator and the entailment validator depend on the NarrationClient protocol,
so both are injectable and offline-gated. build_client() returns None when offline
or when no API key / SDK is available, which the callers treat as 'degrade to
templated'. Tests inject a fake that satisfies the protocol; they never hit the API."""
from __future__ import annotations
import os
from typing import Protocol
from marketbrief.fetch.net import is_offline


class NarrationClient(Protocol):
    def parse(self, *, model: str, system: str, user: str,
              schema: dict, max_tokens: int) -> dict: ...


class AnthropicClient:
    """Real wrapper. Uses structured outputs (output_config.format) on messages.create.

    Returns the parsed JSON object. Numbers are validated downstream; this layer
    does not inspect content."""

    def __init__(self, api_key: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def parse(self, *, model: str, system: str, user: str,
              schema: dict, max_tokens: int) -> dict:
        import json
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)


def build_client() -> NarrationClient | None:
    if is_offline():
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        return AnthropicClient(key)
    except Exception:  # noqa: BLE001 - SDK import/init failure -> degrade
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_narrate_client.py tests/test_config.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/pyproject.toml v2/config.yaml v2/marketbrief/core/config.py v2/marketbrief/narrate/client.py v2/tests/test_narrate_client.py v2/tests/test_config.py
git commit -m "feat(v2): anthropic client seam + narrate config (offline-gated)"
git push origin build/v2
```

---

## Task 5: Ported number-check validator

**Files:**
- Create: `v2/marketbrief/narrate/number_check.py`
- Test: `v2/tests/test_number_check.py`

**Interfaces:**
- Consumes: `ctx.numbers: ComputedNumbers` (`.values: dict[str, float]`), `Cause` (`claim, cause_source_id, verdict`), `Verdict`.
- Produces: `number_check.validate_prose(prose: str, input_numbers: list[float], *, tolerance_pct: float = 0.05) -> ValidationResult` (ported), and a `NumberCheck` class implementing the `Validator` protocol: `judge(self, cause: Cause, ctx: BriefContext) -> Verdict` — returns `Verdict.STRIP` if `cause.claim` contains a number inconsistent with `list(ctx.numbers.values.values())`, else `Verdict.PASS`.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_number_check.py`:

```python
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Cause, ComputedNumbers
from marketbrief.narrate.number_check import validate_prose, NumberCheck


def _ctx(values):
    return BriefContext(
        run_date=date(2026, 6, 22), mode=RunMode.FULL, config=Config(),
        numbers=ComputedNumbers(values=values),
    )


def test_rounded_number_consistent_with_input_passes():
    r = validate_prose("oil traded near 76 dollars", [76.12])
    assert r.ok


def test_invented_number_rejected():
    r = validate_prose("the index rose 12 percent", [0.4, 76.12])
    assert not r.ok
    assert "12" in "".join(r.rejected)


def test_whitelist_skips_dates_times_ordinals_and_instruments():
    r = validate_prose("at 8:30 on Jun 18, the 10-year held its fifth straight session",
                       [])
    assert r.ok  # nothing factual to reject


def test_source_id_token_not_treated_as_number():
    r = validate_prose("yields fell on soft demand (wsj-39)", [])
    assert r.ok  # the '39' in 'wsj-39' must not leak into the number check


def test_validator_strips_cause_with_invented_number():
    nc = NumberCheck()
    ctx = _ctx({"wti": 76.12})
    bad = Cause(claim="oil surged 99 percent on supply fears", cause_source_id="x-1")
    good = Cause(claim="oil traded near 76 dollars", cause_source_id="x-1")
    assert nc.judge(bad, ctx) == Verdict.STRIP
    assert nc.judge(good, ctx) == Verdict.PASS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_number_check.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'marketbrief.narrate.number_check'`

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/narrate/number_check.py`. Port the tolerant number validator from v1 `engine/validator.py` VERBATIM (all regexes, whitelists incl. `_SOURCE_ID_RE` with the `wsj-39` fix, tolerance bands, `extract_numbers`, `_matches_any`, `validate_prose`), then append the `NumberCheck` Validator wrapper. Copy the full body of v1 `engine/validator.py` (lines 22-180: from `import re` through the end of `validate_prose`) into this file unchanged, then add at the end:

```python
# --- v2 Validator wrapper -------------------------------------------------- #
from marketbrief.core.enums import Verdict


class NumberCheck:
    """A number in the claim inconsistent with the computed input set -> STRIP.

    Reads ctx.numbers.values (the same-day ComputedNumbers). The model is told to
    round and approximate, so this is a tolerant consistency check, not identity."""

    def judge(self, cause, ctx) -> Verdict:
        inputs = list(ctx.numbers.values.values())
        result = validate_prose(cause.claim, inputs)
        return Verdict.PASS if result.ok else Verdict.STRIP
```

Keep the file's own `from __future__ import annotations` at the very top (before the ported `import re`). Do NOT import from `engine/` — this is a verbatim copy into the v2 tree, not a cross-import.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_number_check.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/narrate/number_check.py v2/tests/test_number_check.py
git commit -m "feat(v2): port tolerant number-check validator"
git push origin build/v2
```

---

## Task 6: Templated fallback + prompt assembly

**Files:**
- Create: `v2/marketbrief/narrate/templated.py`
- Create: `v2/marketbrief/narrate/prompt.py`
- Test: `v2/tests/test_templated.py`, `v2/tests/test_prompt.py`

**Interfaces:**
- Consumes: `ScoredArticle`, `ComputedNumbers`, `Field`, `NarratedWhy` (`section_id, text, causes, degraded`), `SECTION_KEYWORDS`.
- Produces:
  - `templated.templated_why(section_id: str, numbers: ComputedNumbers) -> NarratedWhy` — a flat, number-only, cause-free line with `degraded=True`. No em dash, no emoji.
  - `templated.templated_all(numbers: ComputedNumbers) -> dict[str, NarratedWhy]` — one per section in `SECTION_KEYWORDS`.
  - `prompt.SYSTEM_PROMPT: str` (the spec §5.6 rubric/system instruction).
  - `prompt.build_user(numbers: ComputedNumbers, matched: dict[str, list[ScoredArticle]]) -> str` — assembles the per-section bundle (numbers + 2-3 matched articles with scores).
  - `prompt.SECTION_SCHEMA: dict` — the json_schema for the model's structured output: an object with one key `sections`, an array of `{section_id, prose, cause, cause_source_id, confidence}` (`cause` and `cause_source_id` nullable).

- [ ] **Step 1: Write the failing tests**

`v2/tests/test_templated.py`:

```python
from marketbrief.core.models import ComputedNumbers
from marketbrief.narrate.templated import templated_why, templated_all
from marketbrief.match.keywords import SECTION_KEYWORDS


def test_templated_why_is_degraded_and_clean():
    w = templated_why("commodities", ComputedNumbers(values={"wti": 76.1}))
    assert w.section_id == "commodities"
    assert w.degraded is True
    assert w.causes == []
    assert "—" not in w.text          # no em dash
    assert all(ord(c) < 128 for c in w.text)  # no emoji / non-ascii


def test_templated_all_covers_every_section():
    out = templated_all(ComputedNumbers(values={}))
    assert set(out.keys()) == set(SECTION_KEYWORDS.keys())
```

`v2/tests/test_prompt.py`:

```python
from marketbrief.core.models import Article, ComputedNumbers
from marketbrief.match.scorer import ScoredArticle
from marketbrief.narrate.prompt import SYSTEM_PROMPT, build_user, SECTION_SCHEMA


def test_system_prompt_states_the_rules():
    s = SYSTEM_PROMPT.lower()
    assert "no clear catalyst" in s
    assert "cause_source_id" in s
    assert "round" in s  # told to round/approximate numbers


def test_build_user_includes_numbers_and_scored_articles():
    matched = {"commodities": [ScoredArticle(
        Article(source_id="cnbc-1", title="Oil jumps", summary="opec"), 0.5)]}
    user = build_user(ComputedNumbers(values={"wti": 76.1}), matched)
    assert "wti" in user and "76.1" in user
    assert "cnbc-1" in user and "Oil jumps" in user


def test_schema_shape():
    props = SECTION_SCHEMA["schema"]["properties"]["sections"]["items"]["properties"]
    assert set(props) >= {"section_id", "prose", "cause", "cause_source_id", "confidence"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_templated.py tests/test_prompt.py -q`
Expected: FAIL — modules missing.

- [ ] **Step 3: Write templated.py**

```python
"""Deterministic fallback 'why' lines (spec §5.6, §7.5 degrade path).

When the model is offline or fails, the brief still ships with flat templated lines
built from numbers and direction alone. No causes, no model. Always degraded=True."""
from __future__ import annotations
from marketbrief.core.models import ComputedNumbers, NarratedWhy
from marketbrief.match.keywords import SECTION_KEYWORDS


def templated_why(section_id: str, numbers: ComputedNumbers) -> NarratedWhy:
    return NarratedWhy(
        section_id=section_id,
        text="No model commentary available; see the figures above.",
        causes=[],
        degraded=True,
    )


def templated_all(numbers: ComputedNumbers) -> dict[str, NarratedWhy]:
    return {sid: templated_why(sid, numbers) for sid in SECTION_KEYWORDS}
```

- [ ] **Step 4: Write prompt.py**

```python
"""System prompt + per-section bundle assembly (spec §5.6 step 4-5).

Hands the model the computed numbers and the 2-3 matched articles per section. The
model extracts reporters' explicit causes, then writes using only those reasons plus
the supplied numbers, rounding and never introducing a number. Structured output
(SECTION_SCHEMA) keeps each claim tagged to its cause_source_id."""
from __future__ import annotations
import json
from marketbrief.core.models import ComputedNumbers
from marketbrief.match.scorer import ScoredArticle

SYSTEM_PROMPT = (
    "You write the 'why' for a daily market brief. You receive computed numbers and "
    "2 to 3 matched news articles per section. Rules, all mandatory:\n"
    "1. Never introduce or alter a number. Use only the numbers supplied. Round and "
    "approximate (say 'about 76 dollars', never '76.23').\n"
    "2. Every causal claim must cite a supplied article by its cause_source_id. If no "
    "article supports a cause, write 'no clear catalyst' and leave cause null. Never "
    "manufacture a cause.\n"
    "3. Plain declarative prose. No em dashes, no emojis.\n"
    "4. Emit structured JSON: one entry per section with section_id, prose, cause "
    "(short phrase or null), cause_source_id (or null), and confidence (low/medium/high)."
)

SECTION_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["sections"],
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["section_id", "prose", "cause",
                                 "cause_source_id", "confidence"],
                    "properties": {
                        "section_id": {"type": "string"},
                        "prose": {"type": "string"},
                        "cause": {"type": ["string", "null"]},
                        "cause_source_id": {"type": ["string", "null"]},
                        "confidence": {"type": "string",
                                       "enum": ["low", "medium", "high"]},
                    },
                },
            }
        },
    },
}


def build_user(numbers: ComputedNumbers,
               matched: dict[str, list[ScoredArticle]]) -> str:
    bundle = {
        "numbers": numbers.values,
        "sections": {
            sid: [
                {"cause_source_id": s.article.source_id,
                 "title": s.article.title,
                 "summary": s.article.summary,
                 "match_score": round(s.match_score, 3)}
                for s in scored
            ]
            for sid, scored in matched.items()
        },
    }
    return json.dumps(bundle, sort_keys=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_templated.py tests/test_prompt.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/narrate/templated.py v2/marketbrief/narrate/prompt.py v2/tests/test_templated.py v2/tests/test_prompt.py
git commit -m "feat(v2): narrate prompt assembly + templated fallback"
git push origin build/v2
```

---

## Task 7: The narrator (GATE 2 close)

**Files:**
- Create: `v2/marketbrief/narrate/narrator.py`
- Test: `v2/tests/test_narrator.py`

**Interfaces:**
- Consumes: `NarrationClient` (`.parse(...)`), `ComputedNumbers`, `matched` map, `NarrateConfig`, `SYSTEM_PROMPT`, `build_user`, `SECTION_SCHEMA`, `templated_all`, `NarratedWhy`, `Cause`.
- Produces: `narrator.narrate(numbers: ComputedNumbers, matched: dict[str, list[ScoredArticle]], *, client: NarrationClient | None, config: NarrateConfig) -> dict[str, NarratedWhy]`. When `client is None` ⇒ `templated_all`. On a client failure or parse error ⇒ `templated_all` (degraded). On success ⇒ one `NarratedWhy` per returned section, each carrying a `Cause` when `cause`/`cause_source_id` are present.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_narrator.py`:

```python
from marketbrief.core.config import NarrateConfig
from marketbrief.core.models import ComputedNumbers, Article
from marketbrief.match.scorer import ScoredArticle
from marketbrief.narrate.narrator import narrate

CFG = NarrateConfig()
MATCHED = {"commodities": [ScoredArticle(
    Article(source_id="cnbc-1", title="Oil jumps", summary="opec"), 0.5)]}


class FakeClient:
    def __init__(self, payload=None, boom=False):
        self.payload = payload
        self.boom = boom

    def parse(self, **kw):
        if self.boom:
            raise RuntimeError("api down")
        return self.payload


def test_offline_client_none_returns_templated():
    out = narrate(ComputedNumbers(values={}), MATCHED, client=None, config=CFG)
    assert out["commodities"].degraded is True
    assert out["commodities"].causes == []


def test_successful_narration_tags_cause():
    payload = {"sections": [{
        "section_id": "commodities", "prose": "Oil rose on OPEC supply news.",
        "cause": "OPEC supply", "cause_source_id": "cnbc-1", "confidence": "high",
    }]}
    out = narrate(ComputedNumbers(values={"wti": 76.1}), MATCHED,
                  client=FakeClient(payload), config=CFG)
    w = out["commodities"]
    assert w.degraded is False
    assert w.text == "Oil rose on OPEC supply news."
    assert len(w.causes) == 1
    assert w.causes[0].cause_source_id == "cnbc-1"


def test_client_failure_falls_back_to_templated():
    out = narrate(ComputedNumbers(values={}), MATCHED,
                  client=FakeClient(boom=True), config=CFG)
    assert out["commodities"].degraded is True


def test_no_cause_yields_causeless_why():
    payload = {"sections": [{
        "section_id": "commodities", "prose": "No clear catalyst.",
        "cause": None, "cause_source_id": None, "confidence": "low",
    }]}
    out = narrate(ComputedNumbers(values={}), MATCHED,
                  client=FakeClient(payload), config=CFG)
    assert out["commodities"].causes == []
    assert out["commodities"].degraded is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_narrator.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'marketbrief.narrate.narrator'`

- [ ] **Step 3: Write the narrator**

```python
"""The narrator: ONE constrained Claude call over the whole picture (spec §5.6).

Injectable client (None when offline / no key). On any failure or offline, returns
templated lines so the brief never blocks. On success, returns one NarratedWhy per
section, each carrying a Cause when the model tagged one. Numbers are validated
downstream by the validator chain; the narrator does not inspect them."""
from __future__ import annotations
from marketbrief.core.models import ComputedNumbers, NarratedWhy, Cause
from marketbrief.core.isolation import run_isolated
from marketbrief.narrate.prompt import SYSTEM_PROMPT, SECTION_SCHEMA, build_user
from marketbrief.narrate.templated import templated_all


def narrate(numbers: ComputedNumbers, matched, *, client, config) -> dict[str, NarratedWhy]:
    if client is None:
        return templated_all(numbers)

    user = build_user(numbers, matched)
    payload, err = run_isolated(
        "narrate:sonnet",
        lambda: client.parse(
            model=config.model, system=SYSTEM_PROMPT, user=user,
            schema=SECTION_SCHEMA["schema"], max_tokens=config.max_tokens,
        ),
        None,
    )
    if payload is None or not isinstance(payload, dict):
        return templated_all(numbers)

    out: dict[str, NarratedWhy] = {}
    for sec in payload.get("sections", []):
        sid = sec.get("section_id")
        if not sid:
            continue
        causes: list[Cause] = []
        if sec.get("cause") and sec.get("cause_source_id"):
            causes.append(Cause(claim=sec.get("prose", ""),
                                 cause_source_id=sec["cause_source_id"]))
        out[sid] = NarratedWhy(
            section_id=sid, text=sec.get("prose", ""),
            causes=causes, degraded=False,
        )
    return out
```

> Note: the `Cause.claim` is the prose itself so the number-check and entailment validators inspect the actual sentence shipped. A `cause` phrase with no `cause_source_id` (or vice versa) yields no `Cause` — the prose still ships but unvalidated, which `TagOnlyCauseCheck` will catch downstream if it contains a causal verb.

- [ ] **Step 4: Run the full suite (GATE 2 verification)**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest -q`
Expected: PASS (all prior tests plus narrator/number-check/templated/prompt).

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/narrate/narrator.py v2/tests/test_narrator.py
git commit -m "feat(v2): narrator one-call structured narration (gate 2)"
git push origin build/v2
```

**GATE 2 COMPLETE** — narrator + number check, injectable client, fake-only tests. Stop for sign-off.

---

## Task 8: Entailment validator

**Files:**
- Create: `v2/marketbrief/narrate/entailment.py`
- Test: `v2/tests/test_entailment.py`

**Interfaces:**
- Consumes: `Cause` (`claim, cause_source_id`), `ctx.articles: list[Article]`, `NarrationClient`, `NarrateConfig`, `Verdict`, `is_offline`.
- Produces: `entailment.EntailmentCheck(client: NarrationClient | None, config: NarrateConfig)` implementing `Validator`: `judge(self, cause, ctx) -> Verdict`. Looks up the article by `cause.cause_source_id` in `ctx.articles`; asks the Haiku model whether it supports `cause.claim`; maps `{"supports","weak","contradicts"}` → `{PASS, HEDGE, STRIP}`. No cause id / no matching article / no client / offline ⇒ PASS (deterministic checks already guarded). A throwing call ⇒ STRIP (raised; caught by `run_chain`'s `run_isolated`).

- [ ] **Step 1: Write the failing test** — `v2/tests/test_entailment.py`:

```python
from datetime import date
from marketbrief.core.config import Config, NarrateConfig
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Cause, Article
from marketbrief.narrate.entailment import EntailmentCheck

CFG = NarrateConfig()


def _ctx(articles):
    return BriefContext(run_date=date(2026, 6, 22), mode=RunMode.FULL,
                        config=Config(), articles=articles)


class FakeClient:
    def __init__(self, verdict="supports", boom=False):
        self.verdict = verdict
        self.boom = boom

    def parse(self, **kw):
        if self.boom:
            raise RuntimeError("haiku down")
        return {"verdict": self.verdict}


ART = Article(source_id="cnbc-1", title="Oil jumps on OPEC cut", summary="opec")
CAUSE = Cause(claim="Oil rose on OPEC supply cut", cause_source_id="cnbc-1")


def test_supports_passes():
    ec = EntailmentCheck(FakeClient("supports"), CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.PASS


def test_weak_hedges():
    ec = EntailmentCheck(FakeClient("weak"), CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.HEDGE


def test_contradicts_strips():
    ec = EntailmentCheck(FakeClient("contradicts"), CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.STRIP


def test_no_client_passes():
    ec = EntailmentCheck(None, CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.PASS


def test_no_cause_source_id_passes():
    ec = EntailmentCheck(FakeClient("contradicts"), CFG)
    causeless = Cause(claim="markets were quiet", cause_source_id=None)
    assert ec.judge(causeless, _ctx([ART])) == Verdict.PASS


def test_missing_article_passes():
    ec = EntailmentCheck(FakeClient("contradicts"), CFG)
    orphan = Cause(claim="x", cause_source_id="nope-9")
    assert ec.judge(orphan, _ctx([ART])) == Verdict.PASS


def test_client_failure_raises_for_chain_to_strip():
    import pytest
    ec = EntailmentCheck(FakeClient(boom=True), CFG)
    with pytest.raises(RuntimeError):
        ec.judge(CAUSE, _ctx([ART]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_entailment.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'marketbrief.narrate.entailment'`

- [ ] **Step 3: Write the entailment validator**

```python
"""Entailment validator (NEW in v2): proves the cited article supports the claim.

Closes v1's tag-only gap (spec §5.6: the tag check 'does not verify that the article
actually supports the cause'). Cheap Haiku call per surviving cause. Appended AFTER
the tag-only and number checks in the chain, so the worst verdict wins. Offline / no
client / no matching article -> PASS (deterministic checks already guarded the cause).
A throwing call is RAISED so run_chain's isolation maps it to STRIP (fail closed)."""
from __future__ import annotations
from marketbrief.core.enums import Verdict

_VERDICT_MAP = {"supports": Verdict.PASS, "weak": Verdict.HEDGE,
                "contradicts": Verdict.STRIP}

_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["verdict"],
    "properties": {"verdict": {"type": "string",
                               "enum": ["supports", "weak", "contradicts"]}},
}

_SYSTEM = (
    "You judge whether a news article supports a causal market claim. Answer with "
    "'supports' if the article clearly supports the claim, 'weak' if it is only "
    "loosely related or partial, and 'contradicts' if it is unrelated or contradicts "
    "the claim. Be strict: a tenuous match is 'weak', not 'supports'."
)


class EntailmentCheck:
    def __init__(self, client, config) -> None:
        self._client = client
        self._config = config

    def judge(self, cause, ctx) -> Verdict:
        if self._client is None or not cause.cause_source_id:
            return Verdict.PASS
        article = next((a for a in ctx.articles
                        if a.source_id == cause.cause_source_id), None)
        if article is None:
            return Verdict.PASS
        user = (f"Claim: {cause.claim}\n"
                f"Article title: {article.title}\n"
                f"Article summary: {article.summary}")
        result = self._client.parse(
            model=self._config.entailment_model, system=_SYSTEM, user=user,
            schema=_SCHEMA, max_tokens=16,
        )
        return _VERDICT_MAP.get(result.get("verdict"), Verdict.HEDGE)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_entailment.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/narrate/entailment.py v2/tests/test_entailment.py
git commit -m "feat(v2): entailment validator (closes v1 tag-only gap)"
git push origin build/v2
```

---

## Task 9: Pipeline wire-up (GATE 3 close)

**Files:**
- Modify: `v2/marketbrief/core/pipeline.py`
- Test: `v2/tests/test_pipeline_narrate.py`, and run the existing e2e offline test.

**Interfaces:**
- Consumes: `derive_numbers`, `match_sections`, `narrate`, `build_client`, `run_chain`, `TagOnlyCauseCheck`, `NumberCheck`, `EntailmentCheck`, all prior.
- Produces: real `_compute`, `_match`, `_narrate` stages wired into `run_pipeline`. `_narrate` runs `run_chain(cause, ctx, [TagOnlyCauseCheck(), NumberCheck(), EntailmentCheck(client, cfg)])` for every cause, replacing each `NarratedWhy.causes` with the judged causes and setting `degraded=True` on the `NarratedWhy` if any cause was stripped. `run_pipeline` gains an optional `narration_client=None` param (defaults to `build_client()`) so tests inject a fake.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_pipeline_narrate.py`:

```python
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Article
from marketbrief.core.pipeline import run_pipeline


class FakeClient:
    """Sonnet narration call returns sections; Haiku entailment returns a verdict.
    Distinguished by the presence of 'sections' in the returned shape."""
    def parse(self, *, model, **kw):
        if "haiku" in model:
            return {"verdict": "supports"}
        return {"sections": [{
            "section_id": "commodities",
            "prose": "Oil rose on OPEC supply cut.",
            "cause": "OPEC", "cause_source_id": "cnbc-1", "confidence": "high",
        }]}


def _ctx():
    return BriefContext(
        run_date=date(2026, 6, 22), mode=RunMode.FULL, config=Config(),
        articles=[Article(source_id="cnbc-1", title="Oil jumps on OPEC cut",
                          summary="opec supply")],
    )


def test_pipeline_narrates_and_validates_with_fake_client():
    ctx = run_pipeline(_ctx(), sources=[], sections=[], news_source=_NoNews(),
                       narration_client=FakeClient())
    why = ctx.narration["commodities"]
    assert why.text == "Oil rose on OPEC supply cut."
    assert why.degraded is False
    assert why.causes[0].verdict == Verdict.PASS


class _NoNews:
    def fetch_news(self, ctx):
        return None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest tests/test_pipeline_narrate.py -q`
Expected: FAIL — `run_pipeline()` has no `narration_client` param / `ctx.narration` is empty.

- [ ] **Step 3: Wire the stages into pipeline.py**

Replace `v2/marketbrief/core/pipeline.py` with (preserving the existing fetch/resolve/assess/assemble stages, adding compute/match/narrate):

```python
from __future__ import annotations
from marketbrief.core.context import BriefContext
from marketbrief.core.models import SourceResult
from marketbrief.core.enums import SourceHealth, Verdict
from marketbrief.core.isolation import run_isolated
from marketbrief.core.registry import discover_sources, discover_sections
from marketbrief.core.health import assess
from marketbrief.fetch.resolver import resolve_fields
from marketbrief.sources.rss_source import RssSource
from marketbrief.compute.derive import derive_numbers
from marketbrief.match.scorer import match_sections
from marketbrief.narrate.narrator import narrate
from marketbrief.narrate.client import build_client
from marketbrief.narrate.chain import run_chain, TagOnlyCauseCheck
from marketbrief.narrate.number_check import NumberCheck
from marketbrief.narrate.entailment import EntailmentCheck


def _fetch(ctx: BriefContext, sources: list) -> BriefContext:
    facts: dict[str, SourceResult] = {}
    for src in sources:
        fallback = SourceResult(name=src.name, health=SourceHealth.FAILED)
        result, err = run_isolated(f"source:{src.name}", lambda src=src: src.fetch(ctx), fallback)
        if err is not None:
            result = SourceResult(name=src.name, health=SourceHealth.FAILED, error=err)
        facts[src.name] = result
    return ctx.with_updates(facts=facts)


def _resolve(ctx: BriefContext) -> BriefContext:
    return ctx.with_updates(resolved_fields=resolve_fields(ctx.facts, ctx.config))


def _fetch_news(ctx: BriefContext, news_source) -> BriefContext:
    result, err = run_isolated("news:rss", lambda: news_source.fetch_news(ctx), None)
    articles = result.articles if result is not None else []
    return ctx.with_updates(articles=articles)


def _assess(ctx: BriefContext) -> BriefContext:
    report = assess(
        ctx.resolved_fields,
        degraded_stale_threshold=ctx.config.resilience.degraded_stale_threshold,
        hard_floor_missing_threshold=ctx.config.resilience.hard_floor_missing_threshold,
    )
    return ctx.with_updates(health=report)


def _compute(ctx: BriefContext) -> BriefContext:
    return ctx.with_updates(numbers=derive_numbers(ctx.resolved_fields, ctx.config))


def _narrate(ctx: BriefContext, client) -> BriefContext:
    matched = match_sections(ctx.articles, ctx.config)
    narration = narrate(ctx.numbers, matched, client=client, config=ctx.config.narrate)
    validators = [TagOnlyCauseCheck(), NumberCheck(), EntailmentCheck(client, ctx.config.narrate)]
    judged: dict = {}
    all_causes = []
    for sid, why in narration.items():
        new_causes = [run_chain(c, ctx, validators) for c in why.causes]
        stripped = any(c.verdict == Verdict.STRIP for c in new_causes)
        judged[sid] = why.model_copy(update={
            "causes": new_causes,
            "degraded": why.degraded or stripped,
        })
        all_causes.extend(new_causes)
    return ctx.with_updates(narration=judged, causes=all_causes)


def _assemble(ctx: BriefContext, sections: list) -> BriefContext:
    built = []
    for sec in sections:
        vm, err = run_isolated(f"section:{sec.id}", lambda sec=sec: sec.build(ctx), None)
        if vm is not None:
            built.append(vm)
    return ctx.with_updates(sections=sorted(built, key=lambda v: v.order))


def run_pipeline(ctx: BriefContext, *, sources: list | None = None,
                 sections: list | None = None, news_source=None,
                 narration_client=None) -> BriefContext:
    sources = discover_sources() if sources is None else sources
    sections = discover_sections() if sections is None else sections
    news_source = RssSource() if news_source is None else news_source
    client = build_client() if narration_client is None else narration_client
    ctx = _fetch(ctx, sources)
    ctx = _resolve(ctx)
    ctx = _fetch_news(ctx, news_source)
    ctx = _assess(ctx)
    ctx = _compute(ctx)
    ctx = _narrate(ctx, client)
    ctx = _assemble(ctx, sections)
    return ctx
```

> If the existing test that injects `narration_client` uses keyword `narration_client=...` but a prior test calls `run_pipeline` positionally, confirm no positional callers break — all current callers pass `sources=`/`sections=`/`news_source=` by keyword (verified in `test_pipeline.py`).

- [ ] **Step 4: Run the full suite + e2e offline (GATE 3 verification)**

Run: `cd /Users/jakeliess/market-brief/v2 && ./.venv/bin/python -m pytest -q`
Expected: PASS (all prior tests + the new pipeline-narrate test).

Then the real e2e offline run:
Run: `cd /Users/jakeliess/market-brief/v2 && MARKET_BRIEF_OFFLINE=1 ./.venv/bin/python brief.py --no-send; echo "exit=$?"; test -f last_run.json && echo "STATE WRITTEN (BUG)" || echo "no state (correct)"`
Expected: `exit=0`, `no state (correct)`, `brief.preview.html` written, no live API call (offline ⇒ templated narration).

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief
git add v2/marketbrief/core/pipeline.py v2/tests/test_pipeline_narrate.py
git commit -m "feat(v2): wire compute/match/narrate + validator chain into pipeline (gate 3)"
git push origin build/v2
```

- [ ] **Step 6 (OPTIONAL): live smoke if a key is present**

Only if `ANTHROPIC_API_KEY` is set and the user opts in. Run a single real narration against `claude-sonnet-4-6` with a tiny canned bundle and assert the structured output parses into `NarratedWhy`. Do NOT add this as a committed test (it costs money and needs a key); run it ad hoc and report the result.

**GATE 3 COMPLETE** — entailment + full pipeline wire-up, end-to-end offline. Sub-project #3 done.

---

## Self-Review

**Spec coverage:**
- Scope decision 1 (plug into existing seam, zero rework) → Tasks 1/8/9 reuse `run_chain`, `Cause`, `NarratedWhy`. ✓
- Decision 2 (matcher port) → Task 1. ✓
- Decision 3 (narrator one Sonnet call, structured) → Tasks 4/6/7. ✓
- Decision 4 (entailment, cheap model, appended) → Task 8 + wired in Task 9. ✓
- Decision 5 (minimal compute, history deferred) → Task 2 (with explicit `test_history_derived_figures_absent`). ✓
- Decision 6 (tests never call live API) → injectable client + fakes throughout; Task 4 offline gate. ✓
- Decision 7 (budget) → one Sonnet + few Haiku calls; entailment only on surviving causes (Task 9 chain order). ✓
- Validator order TagOnly→Number→Entailment → Task 9 `validators` list. ✓
- Failure/degradation (never block) → templated fallbacks (Tasks 6/7), offline gate (Task 4), fail-closed entailment (Task 8). ✓
- Verbatim ports (matcher, number check) → Tasks 1 and 5 copy v1 code unchanged. ✓
- Gates G1/G2/G3 → Tasks 3/7/9 close each. ✓

**Placeholder scan:** The only deliberate placeholders are the `us10y`/`us2y` metric keys in Task 2, which Step 1 of that task resolves against the real symbol table before any code is written — flagged explicitly, not a silent gap. No "TBD"/"handle edge cases"/"similar to" placeholders.

**Type consistency:** `ScoredArticle(article, match_score)` defined in Task 1, used identically in Tasks 3/6/7. `narrate(numbers, matched, *, client, config)` signature consistent Tasks 7/9. `EntailmentCheck(client, config).judge(cause, ctx)` consistent Tasks 8/9. `NumberCheck().judge` and `TagOnlyCauseCheck().judge` match the `Validator` protocol. `NarrationClient.parse(*, model, system, user, schema, max_tokens)` consistent across `client.py`, narrator, entailment, and both fakes.
