# Market Brief v2: Core Engine Design (Sub-Project 1 of 4)

**Status:** Design approved, ready to write implementation plan.
**Date:** 2026-06-20
**Branch:** `build/v2` (lives alongside the working app; old app keeps sending until v2 wins).

## Context and scope

The existing app works (292 tests, 7 phases, sends daily at 8:30 AM CT via GitHub
Actions). It grew organically and is now harder to extend than it should be: the
orchestrator (`brief.py`) does too much imperatively, data sources and brief
sections are not drop-in (adding one means editing the orchestrator and viewmodel),
and data passes as untyped dicts.

v2 is a **re-implementation of the existing product spec**
(`docs/daily_market_brief_SPEC.md`), not a redesign of the product. All product
decisions stay settled (spec §10 decision log is authoritative). v2 changes the
engineering: typed models, an explicit pipeline, and plugin-style sources and
sections.

v2 is decomposed into four sub-projects, built in order, each its own
spec → plan → build cycle:

1. **Core engine + architecture** (this document) — the spine everything plugs into.
2. **Data layer** — provider abstraction, cross-checks, caching, coverage, reliability.
3. **Narrative/AI layer** — latest Claude models, tighter move→cause matching, per-section grounding.
4. **Output/design layer** — modern email template, better charts, optional web companion.

This spec covers **only #1**. It must produce a working end-to-end brief (with
minimal placeholder sources/sections) so #2–#4 have something to plug into.

### Repo strategy (decided)

Same repo, new `v2/` directory, `build/v2` branch. Reuse `docs/` and `data/`
in place. The existing app keeps running until v2 is proven, then we cut over and
delete the old code. This keeps all assets (source-verified data files, CI, secrets,
decision-log history) and allows A/B comparison of output.

## Decisions locked for this sub-project

- **Foundation:** Pydantic v2, typed everywhere — config, facts, view models, and
  stage I/O are all Pydantic models. Validation at every system boundary; fail fast.
- **Plugin contracts:** `DataSource` and `Section` are `typing.Protocol` interfaces
  (structural, no inheritance required). Registries auto-discover plugins.
- **Failure model:** per-plugin isolation. One source or section throwing degrades
  only its own output and never crashes the brief. Matches spec §5.6 / §7.5
  ("never blocks, degrades to templated").

## 1. Architecture: pipeline + two registries

The spine is an explicit, typed pipeline of stages over an immutable
`BriefContext`:

```
load_config + load_state
  -> fetch    (run all registered DataSource plugins -> raw facts)
  -> compute  (derive metrics, diffs, movers from facts -> numbers, in Python)
  -> match    (attach causes from news to moves)
  -> narrate  (model writes the "why", per section, behind validators)
  -> assemble (each registered Section builds its view model from context)
  -> render   (template + charts -> HTML)
  -> send     (relay) + commit_state    [both skipped under --no-send]
```

Two registries make it plugin-style:

- **`DataSource` registry** — each source implements `name`, `fetch(ctx) -> SourceResult`,
  and reports health. Adding a source = drop a file in `marketbrief/sources/` and it
  is auto-discovered. The orchestrator never changes.
- **`Section` registry** — each section implements `id`, `order`, `build(ctx) -> SectionVM | None`,
  `is_quiet(ctx)`. Adding a section = drop a file in `marketbrief/sections/`. The
  floating Top Story slot (spec §4.2) is just a re-sort by computed priority.

The orchestrator (`v2/brief.py`) shrinks to roughly 100 lines: load registries,
run the stages, enforce the hard-floor and degrade gates. All real logic lives in
plugins and the compute/narrate/render modules.

## 2. Module layout

Following "many small files, organize by feature":

```
v2/
  brief.py                 # ~100-line orchestrator: load registries, run stages, gates
  pyproject.toml           # pydantic, yfinance, anthropic, jinja2, matplotlib (pinned)
  marketbrief/
    core/
      context.py           # BriefContext (immutable/frozen Pydantic model)
      config.py            # typed Config loaded + validated from config.yaml
      pipeline.py          # stage runner + isolated-failure wrapper
      registry.py          # DataSource + Section auto-discovery registries
      protocols.py         # DataSource, Section Protocols
      state.py             # load/commit_state; commit is a no-op when send=False
      models.py            # shared Pydantic models (Field, Quote, Move, Cause, SectionVM, ...)
    sources/               # one file per DataSource plugin (auto-discovered)
      prices.py  fred.py  news.py  stocks.py  calendar.py
    sections/              # one file per Section plugin (auto-discovered)
      equities.py  rates.py  commodities.py  movers.py  data_scorecard.py  earnings.py
    compute/               # pure number derivation (metrics, diff, movers selection)
    narrate/               # model client, prompt, validators, matcher
    render/                # template, charts, send
  tests/                   # ported invariants first, then per-plugin tests
```

`sources/` and `sections/` are the only folders that grow over time. Everything in
`core/` is written once. This is what makes sub-projects #2 and #4 drop-in later.

## 3. Data flow: the BriefContext

One immutable (frozen) `BriefContext` threads through every stage. Each stage
returns a **new** context with one field populated (never mutate; always copy):

```
BriefContext (Pydantic, frozen):
  run_date, pull_time, mode (send/no-send), config, prev_state
  facts:     dict[source_name -> SourceResult]   # set by fetch
  numbers:   ComputedNumbers                      # set by compute (diff, movers, metrics)
  causes:    list[Cause]                          # set by match
  narration: dict[section_id -> NarratedWhy]      # set by narrate
  sections:  list[SectionVM]                      # set by assemble
  health:    HealthReport                         # updated as stages run
```

- `fetch` runs all sources in isolation; each returns a `SourceResult` (facts +
  per-source health).
- `compute` reads `facts` and derives all numbers in Python. The model never
  computes or alters a number (spec §1, §2).
- `match` ties moves to news causes (`cause_source_id`), or leaves them uncaused.
- `narrate` writes the "why" per section, each behind validators that may only
  *reference* numbers `compute` produced. A validator failure falls back to a
  templated line and never blocks.
- `assemble` lets each Section build its VM from the now-complete context.
- `render` + `send` finish.

Health gates live in the orchestrator: after `fetch`, too many core fields missing
trips the hard floor; stale core data raises the degrade banner. The set of "core
fields" and both thresholds (`degraded_stale_threshold`,
`hard_floor_missing_threshold`) are ported verbatim from the current app's
`sources/quality.py` + `config.yaml`; the plan must name the exact field list when
porting, not re-derive it.

## 4. Error handling and invariants

Three layers, all from the spec and the project rules:

1. **Per-plugin isolation.** The pipeline wraps every `DataSource.fetch()` and
   `Section.build()` in a guard. A throw is caught, logged with full context,
   recorded as that plugin's `health = failed`, and the run continues. Errors are
   never silently swallowed — they are logged and surface in the health report.

2. **Whole-brief gates** (orchestrator, not plugins):
   - **Hard floor** — too many *core* fields missing -> send the "data unavailable"
     notice, exit non-zero, no normal brief.
   - **Degrade banner** — core data stale or the model failed -> ship the brief with
     the honest banner; sections fall back to templated lines.

3. **Load-bearing invariant (written as a test first):** `--no-send` implies no
   state write. Every state write funnels through `commit_state()`, a hard no-op
   when `mode != send`. The state commit-back to git only happens on Actions, never
   locally (uses `STATE_COMMIT_PAT`).

**Validation at boundaries:** every external input (yfinance/FRED/RSS responses,
`config.yaml`, cached state JSON) is parsed into a Pydantic model at ingress. Bad
external data fails fast into that source's health-failed path; it never propagates
as a half-valid dict.

## 5. Testing

TDD throughout, 80%+ coverage, AAA structure. Order is deliberate — invariants and
contracts first, because they protect everything built after.

1. **Invariant tests first (RED before orchestrator code exists):**
   - `--no-send` => no state write (the load-bearing one).
   - Hard floor trips -> "data unavailable" notice + non-zero exit, no normal brief.
   - Degrade banner fires on stale core / failed model; sections fall back to templated.
   - Per-plugin isolation: a source/section that throws degrades only itself; brief still ships.

2. **Contract tests** — a generic suite every registered `DataSource` and `Section`
   must pass (returns the right Pydantic type, never raises past the guard, reports
   health; sections report quiet/order). New plugins inherit these for free.

3. **Per-plugin unit tests** — compute math, diff logic, movers selection (thin-volume
   floor), matcher, validators (model may only reference computed numbers).

4. **Pipeline integration test** — full run under `MARKET_BRIEF_OFFLINE=1` with
   synthesized clean facts; asserts a complete brief renders deterministically with
   no network.

The existing 292 tests' *intent* is ported where it still applies (quiet-line
suppression, earnings reconcile, stale-line handling, etc.) — rewritten against the
new Pydantic types, not copy-pasted.

The `MARKET_BRIEF_OFFLINE=1` test seam stays so CI and the smoke test run without
network, exactly as today.

## Done when

- `python v2/brief.py --no-send` builds an end-to-end HTML brief offline, with at
  least one real-ish source and a few sections wired through the registries, and
  writes NO state.
- All invariant tests pass (no-send/no-state, hard floor, degrade, isolation).
- Contract tests pass for every registered plugin.
- Coverage >= 80%.
- The orchestrator is ~100 lines; adding a new source or section requires no
  orchestrator edits.

## Out of scope (later sub-projects)

- Real expanded data providers, cross-checks, caching strategy (#2).
- Model prompt tuning, latest-model wiring, advanced matching (#3).
- Final email design, chart redesign, web companion (#4).
- GitHub Actions cutover from v1 to v2 (after v2 is proven).
