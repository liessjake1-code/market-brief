# Market Brief v2: Data Layer Design (Sub-Project 2 of 4)

> Status: APPROVED (brainstorm 2026-06-20). Builds on the Core Engine
> (`docs/superpowers/specs/2026-06-20-v2-core-engine-design.md`, shipped: 38 tests
> green on `build/v2`). Re-implements v1's settled product behavior
> (`docs/daily_market_brief_SPEC.md` §3.1, §5.6, §7, §7.5, Decision 14) on the v2
> typed plugin architecture. Product decisions do NOT change; only the engineering does.

## Goal

Give the v2 engine **good, reliable data**: the correct sourced number for every
metric the brief reports, plus market news, fetched so that no single provider
failure can sink the run. This sub-project is **fetch-only** — it delivers values
and articles; history-derived analysis (diff line, streaks, z-scores, "yesterday")
is a later compute sub-project.

## Scope decisions (locked in brainstorm 2026-06-20)

1. **Port + harden, do not expand.** Same metric set as v1 (no new series). The
   gain is reliability and architecture, not coverage. New data is deferred until
   sub-projects #3/#4 prove it earns its place (YAGNI).
2. **Backup price source: Stooq, best-effort.** Free CSV, no API key. Fills only
   the fields yfinance left missing (primarily the core indices, which Stooq
   covers); tagged as its own source; failure degrades silently, never blocks.
   Rationale: a backup exists to survive a Yahoo block on the *core* fields, which
   is exactly Stooq's coverage. Twelve Data cannot cover indices on its free tier.
3. **Boundary: fetch-only.** Sources expose a raw history-fetch capability but the
   data layer persists nothing. Rolling history, first-run backfill,
   "yesterday = last trading day", streaks, and z-scores belong to the later
   compute sub-project.
4. **News is included** as an editorial source producing `Article`s (not `Field`s).
   The article-to-cause matcher stays in sub-project #3; here we only fetch.
5. **Cross-checks: port v1's oil rule only.** FRED is a date-stamped last resort
   for oil (prefer marking WTI stale over a lagging FRED print, Decision 14); FRED
   is primary for Treasury yields with a yfinance fallback. No new cross-checks.

## Architecture: service plugins + a pure resolver

Chosen over (B) metric-domain plugins that call multiple services internally
(rebuilds v1's god-module, hides per-service failure) and (C) declarative
per-metric policy objects (premature generality for a fixed metric set).

One isolated `DataSource` per **external service**. Each fetches only its own raw
data and knows nothing about the others. A pure, I/O-free **resolver** then merges
the per-service results into the final field set, applying all priority, fallback,
and cross-check rules in one place.

```
discover_sources() -> [YFinanceSource, FredSource, StooqSource, RssSource]
   each runs inside the existing run_isolated() guard
        |-- numeric services  -> SourceResult (raw Fields)
        |-- RssSource         -> NewsResult (Articles)
        v
resolve_fields(per_service_results, config) -> dict[str, Field]   # PURE, no I/O
        v
ctx.with_updates(facts=per_service, resolved_fields=resolved, articles=articles)
        v
assess(resolved_fields, ...)   # existing core, unchanged
```

**Isolation property (the reliability win over v1):** each external service is
independently failable. yfinance down -> its `SourceResult` is `FAILED`, the
resolver falls back to Stooq/FRED per metric, the run continues. v1 threaded
yfinance + Stooq + FRED through interdependent imperative functions; v2 isolates
each service and puts the subtle fallback logic in one pure, fully testable
function — which is exactly where v1's accuracy-critical bugs would hide.

## Reused / new / extended

- **Reused unchanged:** `BriefContext`, `run_isolated`, `assess`, `Field`,
  `SourceResult`, `SourceHealth`, registry auto-discovery, the pipeline skeleton.
- **New:** four service source plugins; `fetch/resolver.py` (pure merge/priority);
  `fetch/net.py` (the only I/O — injectable HTTP helpers); `Article` + `NewsResult`
  models; `core/symbols.py` (ported `SymbolMap` table).
- **Extended:** `BriefContext` gains `resolved_fields: dict[str, Field]` and
  `articles: list[Article]`; the pipeline `fetch` stage calls the resolver after
  the isolated source fetches.

## Module layout

```
v2/marketbrief/
  core/
    models.py            # + Article, NewsResult
    context.py           # + resolved_fields, articles fields
    symbols.py           # NEW: ported SymbolMap table (metric -> yf / stooq / fred)
  fetch/                 # NEW package
    __init__.py
    net.py               # injectable HTTP helpers (timeout, UA); the ONLY network I/O
    resolver.py          # PURE: resolve_fields(per_service, config) -> dict[str, Field]
  sources/
    yfinance_source.py   # YFinanceSource -> SourceResult (raw yf fields + history hook)
    fred_source.py       # FredSource     -> SourceResult (yields + oil last-resort)
    stooq_source.py      # StooqSource    -> SourceResult (best-effort backup)
    rss_source.py        # RssSource      -> NewsResult (articles)
    placeholder.py       # removed once real sources land; its Gate-2/3 tests
                         #   (test_registry/test_plugins/test_pipeline references)
                         #   are migrated to the real sources in the same step
  tests/
    test_symbols.py
    test_resolver.py            # heaviest coverage: every fallback branch
    test_yfinance_source.py
    test_fred_source.py
    test_stooq_source.py
    test_rss_source.py
    test_fetch_integration.py   # pipeline fetch stage end-to-end, offline
```

Each file <800 lines (target 200-400), functions <50 lines.

## Data models

- **Source tags.** `Field.source` is a string; values used: `"yfinance"`, `"fred"`,
  `"fred_last_resort"`, `"stooq"`, `"missing"`. (Kept as strings to match the core
  `Field`; no enum churn.)
- **`Article`** (Pydantic, ported from v1's matcher): `source_id: str`,
  `title: str`, `summary: str = ""`, `url: str = ""`. `source_id` is a stable
  short per-feed-indexed tag (e.g. `"cnbc-3"`) the #3 matcher and cause check
  reference.
- **`NewsResult`** (Pydantic): `name: str`, `articles: list[Article]`,
  `health: SourceHealth = OK`, `error: str | None = None`.
- **`core/symbols.py`**: `SymbolMap(metric, yf, yf_future, fred, fred_units, stooq)`
  and the `SYMBOLS` tuple ported verbatim from v1 (same metric keys: sp500, nasdaq,
  dow, russell, vix, wti, gold, dxy, ust10y, ust2y, btc, eth, copper, cpi_yoy,
  pce_yoy, fed_funds, hy_spread), with a `stooq` symbol added where Stooq covers it
  (the four indices). `CORE_FIELDS` continues to live in `health.py`; `symbols.py`
  does not redefine it.

## The resolver (accuracy-critical core)

`resolve_fields(per_service: dict[str, SourceResult], config: Config) -> dict[str, Field]`
— pure, no I/O. The single home for every fallback/cross-check rule, ported
verbatim from v1 so behavior is identical and the accuracy invariant (numbers from
Python, never invented; spec §1) is preserved by construction:

- **Yields (ust10y, ust2y):** FRED primary; yfinance `^TNX` fallback only if FRED
  is missing; a FRED-only macro series (no yf) degrades to MISSING (it is optional).
- **Oil (wti):** yfinance primary; if missing, mark the field **stale** rather than
  silently substitute; FRED appears only as an explicitly date-stamped last resort
  carrying a note (Decision 14).
- **Everything else:** yfinance primary; **Stooq** fills only the fields yfinance
  left missing, tagged `"stooq"`; otherwise MISSING.
- A metric present from no service -> `Field(metric=k, value=None, source="missing")`.

Because the resolver consumes already-fetched `SourceResult`s and does no I/O,
every branch (FRED-down, yfinance-down, oil-stale, Stooq-fills, both-down,
non-numeric dropped) is a table-driven offline test.

## The sources (each isolated, each offline-testable)

Each source's network access is isolated behind an injectable function
(`fetch/net.py`), exactly as v1 did, so the source logic is unit-tested with
fixtures and never hits the network in tests.

- **YFinanceSource** (`name="yfinance"`): pulls closing prices for each metric's
  `yf` symbol into raw `Field`s; ports v1's MultiIndex/flat `Close` shape handling
  (the load-bearing-pin guard, spec §13) so a benign upstream shape change cannot
  silently zero every pull. Exposes a `fetch_history(days)` hook (no persistence).
- **FredSource** (`name="fred"`): pulls DGS10/DGS2 (yields) and DCOILWTICO (oil
  last-resort) via the FRED API; ports the `units`-transform handling (e.g. `pc1`
  YoY) — the CPI-index-vs-YoY-rate trap is preserved so a wrong number can never
  ship. Requires `FRED_API_KEY` (env only); missing key -> health FAILED, never
  crashes. Drops FRED `"."`/empty observations.
- **StooqSource** (`name="stooq"`): best-effort CSV pull for the indices Stooq
  covers; any failure -> health FAILED with empty fields. Never blocks.
- **RssSource** (`name="rss"`): ports v1's feed set (CNBC, MarketWatch, Fed, WSJ
  free, FT best-effort) and parsing into `Article`s; a single feed failing is
  skipped; total failure -> empty articles, never blocks (spec §5.6).

## Offline seam

`MARKET_BRIEF_OFFLINE=1` (named in the core-engine plan, implemented here): each
source detects the env var and returns synthesized clean fixtures instead of
calling the network, so `python v2/brief.py --no-send` runs the real source/
resolver code path end-to-end with no network and no key.

## Error handling

- **Per-service isolation:** every source runs in the existing `run_isolated`
  guard; a throw records that service `FAILED` and the resolver runs on survivors.
  Never silently swallowed — label + traceback logged to stderr.
- **Validation at ingress:** every external value validated into a Pydantic `Field`
  or `Article`; non-numeric / `"."` / empty observations dropped before they can
  reach a field.
- **Accuracy invariant:** the FRED `units` transform is never dropped silently;
  the oil rule never substitutes a lagging print as if fresh.
- **Secrets:** `FRED_API_KEY` from env only, never hardcoded; absence degrades the
  FRED source rather than crashing the run.
- **News never blocks:** RSS down -> empty articles -> #3 narration falls back to
  templated lines.

## Testing

TDD throughout, AAA structure, >=80% coverage. Order is deliberate:

1. Models + symbols (contracts).
2. **Resolver** — exhaustive branch table (the accuracy core gets the most tests).
3. Each source with injected fixtures (offline): success, partial, total failure,
   FRED `units` transform, FRED `"."` drop, yf shape variants, missing key, RSS
   single-feed-failure.
4. Integration: the pipeline `fetch` stage producing resolved fields + articles
   offline, including a forced yfinance-down run that resolves core fields from
   Stooq/FRED, and an oil-missing run that renders stale (not substituted).

## Done when

- `python v2/brief.py --no-send` runs the **real** sources + resolver offline
  (via `MARKET_BRIEF_OFFLINE=1`), producing resolved fields and articles, writing
  NO state, exit 0.
- A forced yfinance-down run resolves the core fields from Stooq/FRED and the run
  still completes (the reliability bar).
- An oil-missing run renders WTI as stale, never silently substituted.
- The full test suite is green and coverage >= 80%.
- v1 is untouched (root `brief.py`, `engine/`, `render/`, `sources/`).

## Out of scope (later sub-projects)

- Rolling history persistence, first-run backfill, "yesterday = last trading day",
  diff line, streaks, z-scores (compute work; consumes this layer's history hook).
- Article-to-cause matching, entailment validation, model narration (#3).
- Calendar / "What to Watch" / earnings secondary content (revisit with #4 output,
  or a thin add once the core data layer is proven).
- Expanded metric set / additional providers (deferred per scope decision 1).
- Email template, charts, source hyperlinks (#4 output layer).
```
