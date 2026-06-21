# Market Brief v2: Narrative / AI Layer Design (Sub-Project 3 of 4)

> Status: APPROVED (brainstorm 2026-06-20). Builds on the Core Engine
> (`docs/superpowers/specs/2026-06-20-v2-core-engine-design.md`, shipped) and the
> Data Layer (`docs/superpowers/specs/2026-06-20-v2-data-layer-design.md`, shipped:
> 84 tests green on `build/v2`). Re-implements v1's settled "why" behavior
> (`docs/daily_market_brief_SPEC.md` §1, §2, §5.6, §7.5, Decisions 3/8/9) on the v2
> typed plugin architecture, and closes v1's one acknowledged trust gap (the
> tag-only cause check) with a cheap-model entailment pass. Product decisions do NOT
> change; the engineering does, plus the one new entailment guarantee.

## Goal

Turn the v2 engine's resolved numbers and fetched articles into **trustworthy,
source-tagged "why" prose**. Every number traces to a Python computation; every
causal claim traces to a supplied article that actually supports it; "no clear
catalyst" is an encouraged output; and the brief never blocks on the model or news
(it degrades to templated lines). This sub-project fills the deliberate
`compute → match → narrate` pass-through stubs left in the pipeline by #1/#2.

## Scope decisions (locked in brainstorm 2026-06-20)

1. **Three components, plugged into the existing seam, zero core rework.** The core
   engine (#1) already ships the `match → narrate → validate` seam: a frozen
   `BriefContext`, a `Cause`/`NarratedWhy` model pair, a validator-chain runner
   (`marketbrief/narrate/chain.py: run_chain`, worst-verdict-wins, fail-closed via
   `run_isolated`), and the ported `TagOnlyCauseCheck`. This sub-project adds the
   matcher, the narrator, and a second validator behind those existing types.
2. **Matcher: port v1 verbatim, pure, no model.** Port `engine/matcher.py`'s
   keyword/ticker scorer and `SECTION_KEYWORDS` table as-is. It scores each
   candidate `Article` by title (weight 2) + summary overlap and attaches the top
   2–3 with their numeric `match_score`. A below-threshold or empty result is the
   signal that pushes the model toward "no clear catalyst" (spec §4.3, §5.6).
3. **Narrator: one constrained Claude call, latest Sonnet.** Model
   `claude-sonnet-4-6` (spec §5.6 recommended build target; the spec's depth needs
   more than the smallest model), overridable in config. ONE call sees the whole
   picture and emits structured per-section output (per spec §5.6 step 6:
   `{level, change, context, cause, cause_source_id, confidence, prose}`). Numbers
   come only from the Python-computed input set; the model is instructed to round
   and approximate and may never introduce a number. Failure or offline ⇒ templated
   `NarratedWhy` lines. The brief never blocks (spec §5.6, §7.5).
4. **Entailment validator: NEW, cheap model, appended to the chain.** Model
   `claude-haiku-4-5` (the "cheap second pass"), overridable in config. For each
   tagged cause it asks the cheap model whether the cited article actually supports
   the claim, returning PASS / HEDGE / STRIP. This closes v1's documented gap (spec
   §5.6: the tag-only check "does not verify that the article actually supports the
   cause"). It is appended AFTER the ported tag-only and number checks, so the
   worst verdict across all three wins.
5. **Minimal compute in #3, history still deferred.** A small pure `derive.py`
   stage computes ONLY same-day-available figures from `resolved_fields` (per-metric
   change and direction, and same-day spreads such as the 2s10s) into
   `ComputedNumbers`. This gives the number-validator a real input set and the
   narrator real synthesis to write. Rolling-history figures (5/20-day high/low,
   streaks, weekly sums, z-scores, "yesterday") remain deferred to the later compute
   sub-project, exactly as locked in #2's scope. Sections whose synthesis needs
   history get honest short lines now, not invented depth.
6. **Tests never call the live API.** The narrator and the entailment validator take
   an injectable client (the same pattern the data sources use for their
   downloaders). Every test uses a fake client returning canned structured output;
   no `ANTHROPIC_API_KEY` is needed to build or test #3. `MARKET_BRIEF_OFFLINE=1`
   takes the templated path and constructs no client. One OPTIONAL manual smoke at
   the final gate exercises the real wire format if a key is present.
7. **Budget: under a dollar a month (spec §9).** One Sonnet call (~5K in / ~1.5K
   out) plus a handful of Haiku entailment calls per weekday. Both are rounding
   error at one run a day. The entailment pass only runs on causes that survive the
   cheap deterministic checks, bounding Haiku call count.

## Architecture: pure matcher + compute, one model call, a third validator

Chosen over (B) a single mega-prompt that also does matching and number-binding
inside the model (re-introduces exactly the trust problem the design exists to
solve), and over (C) per-section model calls (blinds the model to the cross-asset
causal chain the brief is built around — spec §5.6 "why one call, not eleven").

```
ctx (resolved_fields, articles)
   |
   v   compute stage  (PURE, no I/O, no model)
derive_numbers(resolved_fields, config) -> ComputedNumbers   # same-day figures only
   |
   v   match stage    (PURE, no model)
match_sections(articles, config) -> dict[section_id, list[ScoredArticle]]
   |
   v   narrate stage  (ONE Sonnet call, injectable client; offline/fail -> templated)
narrate(ctx, numbers, matched, client) -> dict[section_id, NarratedWhy]
   |        each NarratedWhy carries its causes (claim + cause_source_id)
   v   validate       (existing run_chain, worst-verdict-wins, fail-closed)
for each cause: run_chain(cause, ctx, [TagOnlyCauseCheck, NumberCheck, EntailmentCheck])
   |
   v
ctx.with_updates(numbers=..., narration={section_id: NarratedWhy}, causes=[...])
```

`compute` and `match` are pure and fully unit-testable with no network and no
model. `narrate` is the only stage that can touch the API, and it is injected and
offline-gated. `validate` reuses the existing isolated chain runner unchanged.

## File layout (new files in this sub-project)

```
marketbrief/
  compute/
    derive.py          # PURE: resolved_fields -> ComputedNumbers (same-day only)
  match/
    keywords.py        # ported SECTION_KEYWORDS + causal regex (single source of truth)
    scorer.py          # ported score_article / match_section -> ScoredArticle
  narrate/
    chain.py           # EXISTS (keep): run_chain + TagOnlyCauseCheck
    number_check.py    # ported tolerant number validator, wrapped as a Validator
    entailment.py      # NEW: EntailmentCheck Validator (haiku, injectable client)
    client.py          # thin Anthropic wrapper + offline/fake seam
    prompt.py          # system prompt + per-section bundle assembly (spec §5.6 rubric)
    narrator.py        # builds prompt, ONE Sonnet call, parses structured -> NarratedWhy
    templated.py       # deterministic fallback NarratedWhy lines (degrade path)
```

Models reused from #1/#2 (no schema changes required): `Cause`, `NarratedWhy`,
`ComputedNumbers`, `Article`, `Field`, `Verdict`. `ScoredArticle` is a small new
internal type in `match/scorer.py` (article + float score), not a `BriefContext`
field.

## Component detail

### Matcher (ported verbatim from v1 `engine/matcher.py`)

- `SECTION_KEYWORDS` and the causal-verb regex move into `match/keywords.py`; the
  causal regex is shared with `TagOnlyCauseCheck` (one definition, imported in both
  places — kill the current duplicate in `chain.py`).
- `score_article(article, keywords)` = `(title_hits*2 + summary_hits) / len(keywords)`.
- `match_section(section_id, articles, extra_keywords=None)` returns the top
  `TOP_ARTICLES` (3) scored articles, or `[]` if the best is below
  `MATCH_SCORE_THRESHOLD` (0.15). Empty ⇒ encourages "no clear catalyst."
- `match_sections(articles, config)` runs every section and returns the per-section
  map handed to the narrator. Watchlist keywords come from config tickers.

### Compute (`compute/derive.py`, pure, same-day only)

- Input: `ctx.resolved_fields` (today's resolved `Field`s) + config.
- Output: `ComputedNumbers(values, diff_lines)`. `values` is the full set the
  number-validator checks against, INCLUDING same-day derived figures the model is
  allowed to cite: per-metric change/percent-change where both legs are present
  today, and same-day spreads (2s10s from the 10y and 2y resolved today).
- Explicitly NOT computed here (deferred to the compute sub-project): 5/20-day
  high/low, streak counts, weekly/multi-day sums, z-scores, prior close, "yesterday".
  Their absence is honest — the narrator gets a thinner input set and writes shorter
  lines for those sections, never invented depth.

### Narrator (`narrate/narrator.py` + `prompt.py` + `client.py`)

- `prompt.py` assembles, per spec §5.6 step 4: the section's numbers (with whatever
  same-day context exists), its 2–3 matched articles with scores, and a one-line
  evergreen domain primer. The system prompt instructs: extract reporters' explicit
  causal claims first, then write using only those reasons plus the supplied
  numbers; round and approximate ("about 76 dollars," never "76.23"); never
  introduce a number; emit "no clear catalyst" when the news is empty; tag every
  cause with its `cause_source_id`.
- ONE `client.messages.parse()` call against `claude-sonnet-4-6` with structured
  output (`output_config.format` / a per-section schema). Returns the structured
  object directly — no hand-parsing. (No assistant prefill; structured outputs
  replace it on Sonnet 4.6.)
- `client.py` wraps the Anthropic client behind a tiny interface the narrator and
  the entailment validator both depend on, so both are injectable and offline-gated.
  `MARKET_BRIEF_OFFLINE=1` ⇒ no client constructed, narrator returns the templated
  path. A live failure (timeout, API error, parse/validation failure surviving one
  retry) ⇒ templated path, run flagged degraded (spec §7.5).
- Output: `dict[section_id, NarratedWhy]`, each carrying its `Cause`s.

### Validators (the chain, after narration)

Order (worst verdict wins, fail-closed already implemented in `run_chain`):

1. `TagOnlyCauseCheck` (exists) — a causal verb with no `cause_source_id` ⇒ STRIP.
2. `NumberCheck` (ported from v1 `engine/validator.py`) — every number in the prose
   must be consistent with the `ComputedNumbers` input set within tolerance;
   whitelists clock times, dates, ordinals, instrument names, source-id tokens
   (the 2026-06-18 `wsj-39` fix included), and bare years. A number matching nothing
   ⇒ STRIP. Wrapped as a `Validator` that reads `ctx.numbers`.
3. `EntailmentCheck` (NEW) — for a cause that passed 1 and 2, ask `claude-haiku-4-5`
   whether the cited article (looked up by `cause_source_id` in `ctx.articles`)
   supports the claim. Verdict: PASS (clearly supports) / HEDGE (weak/partial) /
   STRIP (contradicts or unrelated). Injectable client; offline ⇒ skips to PASS
   (the cheap deterministic checks still ran); a throwing call ⇒ STRIP via the
   existing isolation guard.

STRIP ⇒ the section's "why" degrades to a templated line; HEDGE ⇒ the prose is kept
but softened/flagged per the existing `NarratedWhy.degraded` handling.

## Failure & degradation (spec §5.6, §7.5 — never block)

- News (RSS) unavailable ⇒ empty article map ⇒ matcher returns `[]` everywhere ⇒
  narrator writes "no clear catalyst" lines. No degrade flag required (this is a
  valid honest state).
- Model call fails or offline ⇒ templated `NarratedWhy` lines from numbers +
  direction alone; run logged degraded and banner-flagged.
- Entailment model fails ⇒ that single cause fails closed to STRIP (one section
  degrades), the rest of the brief is unaffected. Entailment offline ⇒ PASS-through
  (deterministic checks already guarded the cause).
- A validator throwing is already caught by `run_isolated` and mapped to STRIP.

## Gates (TDD; stop for sign-off at each)

- **G1 — matcher + compute (PURE, no model).** Port the scorer + keyword tables
  into `match/`; build `compute/derive.py`. Tests prove scoring/threshold parity
  with v1 (same inputs → same `ScoredArticle` ordering and the same empty-on-low
  behavior) and prove same-day derivations (change, 2s10s) while confirming
  history-derived figures are absent. No API, no client.
- **G2 — narrator + number-check validator.** Injectable `client.py` + a fake
  client; `prompt.py` assembly; `narrator.py` ONE-call structured parse →
  `NarratedWhy`; ported `NumberCheck` wired into the chain after `TagOnlyCauseCheck`;
  `templated.py` fallback; `MARKET_BRIEF_OFFLINE` seam. Tests (fake client only)
  prove: tagged prose round-trips; an invented number ⇒ STRIP; a client failure ⇒
  templated fallback + degraded flag; offline ⇒ templated, no client constructed.
- **G3 — entailment validator + full pipeline wire-up.** `EntailmentCheck` on Haiku
  appended to the chain (fake client); pipeline `compute/match/narrate` stubs
  replaced with the real stages; `_narrate` runs `run_chain` per cause with all
  three validators. End-to-end offline run (`MARKET_BRIEF_OFFLINE=1 python
  brief.py --no-send`) produces validated `NarratedWhy` per section, exit 0, no
  state write, no live call. OPTIONAL: one manual live smoke if a key is present,
  asserting the real structured-output wire format parses.

## What is explicitly NOT in this sub-project (YAGNI / deferred)

- Rolling history, streaks, weekly sums, z-scores, "yesterday" (compute sub-project).
- Body-fetching of article HTML (spec §5.6: headlines + summaries only at launch;
  body fetch is a post-launch flag).
- The email template, charts, and any rendering changes (sub-project #4 — the
  renderer keeps consuming `NarratedWhy` as it does today).
- Any change to the v1 app (root `brief.py`, `engine/`, `render/`, `sources/`),
  which keeps running until v2 wins.

## Verbatim ports (do not redesign)

- `engine/matcher.py`: `SECTION_KEYWORDS`, `_CAUSAL_RE`, `score_article`,
  `match_section`, `MATCH_SCORE_THRESHOLD`, `TOP_ARTICLES`.
- `engine/validator.py`: the tolerant number check end to end — `_NUMBER_RE`, all
  whitelist regexes (clock, date, ordinal, instrument, `_SOURCE_ID_RE` incl. the
  `wsj-39` fix, year), `extract_numbers`, `_matches_any` tolerance bands
  (`DEFAULT_TOLERANCE_PCT`, `PRICE_TOLERANCE_ABS`, `BPS_TOLERANCE`), `validate_prose`.
- Spec §5.6 model rubric and the structured per-section field shape
  (`{level, change, context, cause, cause_source_id, confidence, prose}`).

## Build facts (for the executor)

- Tests: `cd v2 && ./.venv/bin/python -m pytest`. Git from repo root with `v2/` paths.
- venv is uv-managed (NO pip). Add the SDK with
  `uv pip install --python .venv/bin/python anthropic` and add `anthropic` to
  `v2/pyproject.toml` (pin per spec §8.2 load-bearing note).
- Model IDs live in `v2/config.yaml` (`narrate.model: claude-sonnet-4-6`,
  `narrate.entailment_model: claude-haiku-4-5`), read through `Config`.
- Offline seam: `MARKET_BRIEF_OFFLINE=1` (reuse `marketbrief/fetch/net.py:is_offline`).
- Branch `build/v2`, mirrors to origin; NOT main; no auto-PR. Commit + push +
  update memory at each gate.
