# v2 Sub-project #4: Output / Design

Status: design approved, ready for implementation plan
Branch: build/v2 (mirrors to origin; not main, no auto-PR)
Source of truth: `docs/daily_market_brief_SPEC.md` §1 (fencing), §2 (house style),
§4 (structure), §5 (Top Story engine), §6 / §6.5 (charts + visual design),
§7.5 (resilience / degrade banner). Settled decisions in §10 are not re-litigated.

## 1. Purpose and scope

Build the final output layer of v2: turn the frozen, typed `BriefContext` produced by
the existing pipeline (fetch → resolve → news → assess → compute → narrate) into an
email-ready HTML brief with inline CID charts, matching v1's shipped "The Tape" design
in structure while refreshing its visual layer within the firm rules of spec §6.5.

This is the last sub-project. Once it is built and proven, v2 reaches parity with v1
and we cut over (separate step). Until cutover, v1 keeps running untouched.

### In scope

- All 11 sections (§4.3) as typed view models: US Equities, Rates and the Dollar,
  Commodities, Washington and Policy, Movers, Economic Data Scorecard, Earnings on Deck,
  Watchlist, Crypto, Volatility and Breadth, What to Watch Today.
- The top blocks: diff line (§4.1), At-a-Glance table (§4.1), the live pre-market fence
  (§1, §3.1, §6.5), the degrade banner (§6.5, §7.5), the Top Story float ordering (§4.2, §5).
- The three default-on charts (§6): equities daily %-change bar, 10Y trend + yield curve,
  WTI 1-month trend. Off-by-default charts behind config toggles.
- Email-ready output: the dumb Jinja template (refreshed "The Tape"), CID chart rendering,
  and MIME multipart assembly. Fully testable offline.
- The hard-floor "data unavailable" notice path (§7.5).

### Out of scope (explicitly deferred)

- Live email send (Brevo/SMTP `send.py`), GitHub Actions cron, and secrets wiring.
  These are the cutover step, done when we flip v2 live. #4 performs NO outward-facing
  actions and touches NO secrets.
- A standalone web companion (YAGNI; the email HTML opens in a browser as-is).
- Rolling-history-dependent features beyond what `ctx` already carries (history is still
  deferred per the narrative-ai sub-project).

## 2. Approach (selected: A — Rich SectionVM + per-section builders)

Three independently testable layers sit between `BriefContext` and the email. The
trust-critical rules (stale-field exclusion, settled/live fence, mechanical-move
annotation, grounding) live in typed Python, never in the template. The template is a
dumb renderer that walks typed view models. This honors v2's established idiom — typed,
frozen, auto-discovered, small files — and keeps the refreshed-visuals work safe to
iterate because no logic lives in the template.

Rejected alternatives:
- B (port v1's 616-line monolithic `viewmodel.py` mostly intact): drops an untyped
  monolith into a typed/frozen/small-files codebase; fights the <800-line and
  immutability rules; the dict output loses type safety; hard to build/test in parallel.
- C (logic in Jinja): business logic in templates is untestable without rendering and
  buries the fence/stale/grounding rules that must be unit-tested. Rejected on §2 grounding.

## 3. Architecture and data flow

```
BriefContext (frozen)
  → section builders   (marketbrief/sections/*.py, one file per section)
       each implements the existing Section protocol, returns an enriched SectionVM
  → assemble layer     (marketbrief/assemble/*.py, pure functions)
       diff line, At-a-Glance, Top Story float ordering, live fence, degrade banner
       → composes a BriefView
  → render layer       (marketbrief/render/)
       charts.py  (matplotlib → PNG bytes → ChartRef CID)
       template.html.j2  (dumb; walks typed view models)
       mime.py    (multipart assembly, inline CID parts)
  → email-ready HTML + CID chart attachments
```

The existing `run_pipeline` keeps its `_assemble` step (which already calls each section's
`build(ctx)` via the registry) but the sections it builds now return the enriched
`SectionVM`; an assemble layer then composes those into a `BriefView`, and a final render
step turns the `BriefView` into HTML + CID charts. `--no-send` writes `brief.preview.html` and never
sends or writes state — the existing invariant is unchanged.

### Layer responsibilities

1. **Section builders** — `marketbrief/sections/<section>.py`. One file per section,
   implementing the existing `Section` protocol (`id`, `order`, `build(ctx) -> SectionVM | None`,
   `is_quiet(ctx)`), auto-discovered by the existing registry. Each consumes `ctx`
   (resolved fields, numbers, narration) and returns an enriched typed `SectionVM`,
   including its honest quiet-line fallback (ported from v1's `QUIET_LINES`; e.g.
   "Indices little changed; no clear catalyst."). Each file stays under ~150 lines and
   owns exactly one section's editorial logic.

2. **Assemble layer** — `marketbrief/assemble/`, pure functions over `ctx` + built sections:
   - `diff_line.py` — "what changed since yesterday" from `ctx.prev_state` + current
     settled fields; excludes stale fields; honest no-change line when nothing flipped.
   - `glance.py` — the At-a-Glance `GlanceRow`s; the "This morning" row is the only
     `is_live=True` row.
   - `topstory.py` — pure §5 ordering: tier-one calendar event → mechanical-move
     suppression (`data/mechanical_moves.yaml`) → largest standardized move over trigger
     → fixed fallback order (§4.2). Sets `is_promoted` on the lead.
   - `fence.py` — builds the `LiveSnapshot` with the time-aware label
     ("Pre-market as of HH:MM CT" before 8:30 CT, else "Early session as of HH:MM CT", §3.1).
   - `banner.py` — degrade-banner text from `ctx.health` (model failed, or
     ≥ `resilience.degraded_stale_threshold` stale fields); hard-floor path
     (≥ `resilience.hard_floor_missing_threshold` missing → unavailable notice, exit non-zero).
   - `brief_view.py` — composes the `BriefView`.

3. **Render layer** — `marketbrief/render/`:
   - `charts.py` — ported from v1, restyled to §6.5 palette; returns `ChartRef`.
   - `template.html.j2` — The Tape structure, refreshed visuals, dumb renderer.
   - `mime.py` — multipart assembly with inline CID charts.
   - `render_unavailable_notice()` retained for the hard floor.

## 4. Enriched view-model types

Added to `core/models.py` as frozen Pydantic models (immutable, like the rest of v2).
Ported from v1's `FigureCell`/`GlanceRow`/`HBar`/`Spark`/`SectionView`/`BriefView`, now typed.

```
FigureCell   metric_label: str, value_str: str, change_str: str,
             direction: Direction (up|down|flat), source_url: str | None,
             stale: bool = False, mechanical: bool = False
StatRow      label: str, cells: list[FigureCell]
WhyLine      text: str, source_url: str | None, source_label: str | None,
             hedged: bool = False
ChartRef     cid: str, alt: str, kind: ChartKind (bar|line|curve|spark)
GlanceRow    category: str, latest: str, why_brief: str, is_live: bool = False
MoverRow     ticker: str, favicon_url: str | None, value_str: str,
             direction: Direction, why: str, source_url: str | None
SparkRef     ticker: str, cid: str

SectionVM (enriched — replaces the stub)
             id: str, title: str, order: int, quiet: bool
             lead: WhyLine                 # the one-line "why" (always present)
             stat_rows: list[StatRow]
             why_lines: list[WhyLine]       # the deep read (empty when quiet)
             charts: list[ChartRef]
             movers: list[MoverRow]         # Movers only
             sparklines: list[SparkRef]     # Watchlist only
             is_promoted: bool = False      # set by Top Story float

LiveSnapshot as_of_label: str, rows: list[FigureCell], is_premarket: bool
BriefView    diff_line: str, glance_rows: list[GlanceRow],
             sections: list[SectionVM],    # already in Top Story order
             live: LiveSnapshot | None, degraded: bool, banner_text: str | None
```

`Direction` and `ChartKind` are enums in `core/enums.py`.

Three spec rules enforced by the types, so the template cannot violate them:
- **`stale: bool` on every `FigureCell`.** Assemble excludes stale fields from the diff
  line, the Top Story engine, and the why-lines (§7.5); the template only renders the marker.
- **`LiveSnapshot` is a separate top-level type on `BriefView`,** not another section.
  The settled/live fence (§1, §6.5) is structural: a pre-market figure cannot appear in a
  settled `StatRow`.
- **`WhyLine.source_url: str | None` + `hedged`.** A why with no source must be hedged or
  be the "no clear catalyst" line (§2 grounding). Section builders set `hedged=True` whenever
  `source_url is None`; a test enforces this invariant.

## 5. Charts (port + restyle)

Port `render/charts.py` from v1 (already produces the three default-on charts). Restyle to
the §6.5 palette: ink navy `#13202E`, gold rule `#B0892F`, direction green `#197A4B`,
direction red `#BC3B2E`, muted grey `#6B7785`, paper `#FBFAF7`; tabular numerals.

- Default on (§6): equities daily %-change bar, 10Y trend + yield-curve snapshot,
  WTI 1-month trend.
- Off by default behind config toggles: VIX trend, movers bar, crypto trend, scorecard bar,
  watchlist sparklines (sparklines auto-on once the watchlist is populated).

`Config` gains a `ChartsConfig` carrying the default-on/off toggles. Each chart renders to
in-memory PNG bytes keyed by a CID and returns a `ChartRef`. On offline or chart failure the
section renders without its chart and never blocks (§7.5).

## 6. Template and visual refresh (frontend-design ON)

The Tape's structure ported to a new `render/template.html.j2`: masthead, diff line,
At-a-Glance card, ordered sections, the visually fenced live block, What to Watch Today.

Email-safe build constraints (§6.5, firm): single-column table layout, fully inline styles,
web-safe font stack — Georgia (or serif fallback) for the masthead, `Consolas,
"SFMono-Regular", monospace` for every figure. The frontend-design plugin is turned ON to
refresh the visual layer (type scale, spacing, card treatment, the single gold rule) within
§6.5's firm rules:

- One accent. Green and red carry direction only; everything else is navy, paper, grey, and
  the one gold rule. No second accent.
- Tabular monospace numerals are the signature element and are protected.
- The live pre-market zone is visually fenced (tinted block or labeled rule) and every figure
  in it carries its pull timestamp.
- Favicons (16px, Google favicon service) appear only in Movers and Watchlist rows. A failed
  favicon still leaves the row readable from ticker + text.
- Degrade banner: a small marked block at the top of the brief when `BriefView.degraded`.
- No em dashes, no emojis, plain declarative prose (§2).

The template is dumb: it walks typed view models and emits HTML with zero business logic.
`render/mime.py` assembles a multipart message with inline CID chart parts.
`render_unavailable_notice()` is retained for the hard-floor path.

## 7. Pipeline wiring

`run_pipeline` gains the enriched `_assemble` (build sections via the registry, then run the
assemble layer to compose a `BriefView`) and a final render step (charts → template → HTML,
plus MIME assembly available to the cutover step later). No new outward-facing behavior:
`--no-send` writes `brief.preview.html`, does not send, and does not write `last_run.json`.
The hard floor (≥ `hard_floor_missing_threshold` core fields missing) writes the unavailable
notice and exits non-zero. Live SMTP send, the Actions cron, and secrets remain out of scope.

## 8. Testing

- **Section builders:** quiet vs full read per section; stale-field exclusion; the quiet
  fallback matches the spec's honest "no clear catalyst" lines.
- **Assemble:** diff-line stale exclusion; Top Story promotion order and mechanical-move
  suppression on listed dates; fence label time-awareness (before vs after 8:30 CT); banner
  threshold; hard-floor path.
- **Type invariants:** a `WhyLine` with `source_url is None` and `hedged=False` is never
  produced by a section builder; a pre-market figure never appears in a settled `StatRow`.
- **Render:** snapshot test of the template against a fixed `BriefView`; MIME has the expected
  CID parts; an offline run still produces HTML with charts absent.
- **E2e offline:** `MARKET_BRIEF_OFFLINE=1 ./.venv/bin/python brief.py --no-send` exits 0,
  writes no `last_run.json`, and writes `brief.preview.html` containing all 11 sections,
  the diff line, At-a-Glance, the fenced live block, and What to Watch Today.

Coverage target ≥ 80% (project standard). Tests never hit the live API or network (the
existing offline seam and fake clients are reused).

## 9. Done when

- All 11 sections render with real numbers, sourced why-lines, and honest quiet lines.
- Diff line, At-a-Glance, live fence, degrade banner, and Top Story float all work and are
  unit-tested, with the trust rules (stale exclusion, fence, mechanical suppression,
  grounding) enforced in Python and verified.
- The three default-on charts render as inline CID images; off-by-default charts respect
  their toggles; sparklines auto-on with a populated watchlist.
- The refreshed template renders email-safe HTML within §6.5; MIME assembles with CID parts.
- E2e offline run is green per §8; no live send, no Actions, no secrets touched.
- Full test suite green (existing 122 plus the new tests), coverage ≥ 80%.
