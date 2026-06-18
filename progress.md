# Progress Log

A running record of build progress across Claude Code sessions. Track A = human
(external steps); Track B = Claude Code (the code). See `START_HERE.md` and
`docs/claude-code-execution-guide.md` for the full two-track split.

This file is committed to the repo. NEVER put secret values here, only the names
of secrets and whether they are set.

---

## Status at a glance

- **PER-STOCK WATCHLIST/MOVERS FEATURE — DONE (2026-06-18), build/phases 2311c13,
  mirrored to main 9ad4ce5, 282 tests green (+48 over the session-start 234).**
  The deferred big chunk. Watchlist and Movers are now real per-stock sections, all
  numbers Python-computed (the model writes ZERO numbers, spec §1). Built TDD in 6
  slices, each committed + pushed; the look slices verified via the preview-loop
  screenshot before shipping. User decisions (all "recommended"): separate `stocks`
  state namespace @ 10 closes; session/week/month windows (match other sections);
  full per-stock model "why" now; compact per-stock "why" lines under the table.
  What shipped:
  1. STATE: new top-level `stocks` map in last_run.json, parallel to + kept apart
     from `metrics` (engine/state.py: State.stocks + stock_history/_dates/_volume
     accessors, _empty_stock, seed_stock_state, STOCK_HISTORY_KEEP=10, save trims in
     lockstep). Backward compatible — an older file with no `stocks` key loads clean.
  2. FETCH: sources/stocks.py — best-effort batch pull (closes, ISO dates, latest
     volume) for arbitrary tickers, separate from the metric-keyed prices.py. A
     failed/empty ticker is omitted; never raises, never trips the banner/hard floor
     (core-metric/model only). Reuses prices._select_close MultiIndex handling +
     a Volume analogue. Validated against live yfinance (NVDA/TSLA/QUBT real data).
  3. MOVERS: engine/movers.py — pure spec §7 best-effort selection: watchlist-only by
     default, upgrade to the curated universe only when the screen is RELIABLE (>=
     half the configured universe returned), else degrade to watchlist-only rather
     than print noise; movers_min_volume gates universe names (watchlist bypasses),
     flat/uncomputable excluded, capped to MAX_MOVERS.
  4. RENDER: stats.stock_stat_row (ticker-labeled %-change row); viewmodel
     build_stock_table / build_movers_table / build_stock_sparklines / build_stock_notes;
     build_sections gains stock_tables/stock_sparklines/stock_notes. Watchlist
     sparklines are now REAL per-stock series for ALL tickers (SPCX/QUBT included),
     fixing the old accident where only tickers doubling as core metrics drew one.
  5. WHY: each surfaced ticker (watchlist + selected movers) is a "stock:<TICKER>"
     pseudo-section folded into the SAME single narrative call, matched on ticker +
     company name (from ticker_domains). Same validator path — a cause with any
     number is rejected; a sourced cause resolves to a clickable citation; "no clear
     catalyst" is accepted and the stock is then OMITTED from the notes (never a
     fabricated reason, spec §2). Rendered as compact "TICKER reason (source)" lines
     under the Movers/Watchlist table.
  6. WIRING: brief._gather_stocks (offline -> {}), select_movers, _run_narrative folds
     stock bundles, _build_view builds the tables/sparklines/notes, _commit_state
     appends today's close/date/volume per pulled stock (seeding new tickers). No-send
     no-state invariant covers stocks too. Real-data no-send build pulled 7/7 tickers
     and rendered both tables + sparklines + why notes.
  New files: sources/stocks.py, engine/movers.py, tests/test_stocks_state.py,
  test_stocks_fetch.py, test_movers.py, test_stocks_view.py, test_stocks_narrative.py.
  NEXT (Track A / go-live): restore allow_repeat_send -> false; watch scheduled
  mornings; the next real send proves per-stock fetch + "why" on the runner.

- **NODE 20 ACTIONS CHORE — DONE (2026-06-18), build/phases fe8b3d3, mirrored to
  main a782e07.** GitHub deprecated the Node 20 actions runtime; `actions/checkout@v4`
  and `actions/setup-python@v5` emitted a deprecation warning on every run and would
  eventually hard-fail when the Node 20 runner is retired. Bumped both daily-brief.yml
  and smoke-test.yml to the first majors on Node 24: `checkout@v5` + `setup-python@v6`.
  No behavior change (python-version 3.12 + the STATE_COMMIT_PAT checkout token are
  unchanged); workflow-only, no Python touched, test suite unaffected. Track A proof
  (warning gone) is the next workflow run's log. Open: deferred per-stock watchlist.

- **LOOK FIXES FROM THE REAL-SEND SCREENSHOTS — DONE (2026-06-18), build/phases
  af579a9, mirrored to main 75c1cb4, 234 tests green (+8).** The human had the
  delivered email open in Outlook and shared screenshots. Three fixes shipped, each
  verified through the preview-loop screenshot before commit:
  1. MACRO BACKDROP STRIP (the em-dash rows): CPI YoY, PCE YoY, and Fed funds were
     sitting in the per-section session/week/month CHANGE table showing perpetual em
     dashes (they had only 1 stored data point) and would only ever show meaningless
     ~0 daily deltas (these update monthly / at FOMC). Decision (human): take them OUT
     of the change table and show them a different way. New `Metric.monthly` flag +
     `is_monthly()` (engine/metrics.py); viewmodel `SECTION_STAT_METRICS` for
     rates_and_dollar is now ONLY daily-trading series (ust10y, ust2y, dxy, hy_spread)
     + the synthetic 2s10s spread row — all with real numbers. New `SECTION_MACRO_METRICS`
     + `MacroReading` + `build_macro_strips()` render CPI/PCE/Fed funds as a compact
     current-level strip ("CPI INFLATION (YOY) 4.17%  PCE ... 3.77%  FED FUNDS 3.63%")
     under the rates table via a new `macro_strip` template macro. Copper stays in the
     commodities change table (it trades daily). brief.py `_build_view` wires
     `macro_strips`; preview_fixture.py exercises it.
  2. CHART X-AXIS LABEL COLLISION ("Jun JuJu 18"): `charts._date_xaxis` rewritten to
     pick evenly spaced ticks snapped to dated points and force a minimum index gap
     (`_MIN_TICK_GAP`) so adjacent date labels never overlap. Both PNG charts now read
     "May 21 - May 28 - Jun 3 - Jun 10" cleanly.
  3. 10-YEAR LINE LOOKED LIKE A SAWTOOTH: `charts._pad_ylim` floor raised from 1% to
     3% of level with a 2x headroom multiplier, so a near-flat real ~15 bps month sits
     gently in the MIDDLE of the panel instead of filling it edge to edge. Still
     truthful (the real peak/dip remain visible), just no longer magnified into noise.
     Verified against a realistic jagged 4.42-4.58 fixture, not just the smooth ramp.
  Accuracy unchanged: every figure still computed in Python; the model writes none.
  New tests: monthly flag (test_macro_metrics), tick separation + no-dup final tick +
  pad-ylim-calm (test_charts), rates table excludes monthly + macro strip readings/skip/
  section wiring (test_viewmodel). NOTE on the em dashes the human saw: the OTHER em
  dashes (copper session/week/month) are NOT a bug and were left as-is — copper has only
  1 stored data point so far and self-heals as history accrues (session next run, week
  ~5 sessions out, month ~21). Only the monthly series were restructured. NEXT: deferred
  per-stock watchlist/movers feature; open chore: pin actions/checkout + setup-python off
  Node 20 (cosmetic).

- **REAL-SEND PROOF LANDED (2026-06-18):** A real send (commit 3c89da6 on main,
  state + runs/ dump committed) PROVED the three open unknowns at once, verified by
  reading the committed last_run.json + runs/2026-06-18.json:
  1. NARRATIVE UN-DEGRADE: the model produced real NUMBER-FREE sourced causes with
     valid cause_source_ids (us_equities wsj-22, rates_and_dollar wsj-39, commodities
     wsj-20, volatility_breadth cnbc-14; crypto correctly "no clear catalyst"/None).
     First clean non-templated prose run.
  2. NEW MACRO METRICS FETCH LIVE from the runner: copper 6.38 (yfinance HG=F),
     cpi_yoy 4.17%, pce_yoy 3.77%, fed_funds 3.63%, hy_spread 2.63% (FRED). The
     units=pc1 YoY transform fired correctly (CPI is a 4.17% RATE, not a raw index in
     the hundreds) — structural accuracy holds in production.
  3. DELIVERY: Brevo DELIVERED (11 sends today during testing); the email reached the
     Tulane server and landed in JUNK (released by human). NOT a code bug — a
     free-relay-sender reputation issue from 11 sends/day; one-per-morning at go-live
     is far less likely to quarantine. allow_repeat_send TEMPORARILY true is what let
     all 11 send — restore to false at go-live.
  Independent read-only audits this session (macro-metric plumbing + chart/viewmodel/
  send paths) found NO bugs: units transform can't be silently dropped, new metrics
  excluded from CORE_FIELDS so they never trip the banner, bps-vs-pct correct,
  rebase divide-by-zero guarded, em-dash for thin history, Outlook MIME tree intact.
  Backward-compat state seeding proven against the real last_run.json (all 5 new keys
  fold in, correct change field). 226 tests green on py3.12. NEXT: human has the email
  open and wants LOOK fixes + has questions (new chat); then build the deferred
  per-stock watchlist/movers table. Open low-risk chore: pin actions/checkout +
  actions/setup-python off Node 20 (deprecation warning, cosmetic).

- **GO-LIVE IN PROGRESS (2026-06-18):** All 7 phases built + merged to `main`
  (default branch, so the daily-brief.yml crons register and fire). Real sends
  land in the Tulane inbox. Now iterating on look + content quality before
  locking down. 149 tests green on py3.12.
- **EMAIL REDESIGN — ALL 9 ITEMS DONE (2026-06-18):** Human disliked the look;
  approved a full redesign via visual previews -> see **HANDOFF_DESIGN.md** for the
  locked decisions. New look is "The Tape" on WHITE (serif masthead/headings, IBM
  Plex Mono numbers, inline hybrid charts, clickable per-section source citations).
  Items 1-9 are now SHIPPED on build/phases (172 tests green on py3.12, +12 over the
  prior 160). What changed this session (items 2-9):
    2. Rich cause-free computed fallback `templated.computed_section_line` — the
       §5.6 four-ingredient read MINUS the "why" (level-in-context, move, range/
       streak, forward hook). Quiet sections are substantive, never a fake cause.
    3. WSJ free RSS feeds added (Dow Jones host: RSSMarketsMain, RSSWorldNews —
       both verified resolving from the build host) + FT markets feed best-effort
       (graceful-fail; FT blocks automated fetch). `_prefix_for` wsj/ft entries.
       Free RSS + headline links ONLY (no paywall scraping) per the WSJ/FT decision.
    4-5. Viewmodel threads per-section citations, inline HTML charts (Top Story
       index bars, watchlist sparklines), the 4 glance text rows + short direction
       tags, skips what_to_watch in the body, favicon-as-text. `render/
       template.html.j2` REPLACED with the white "The Tape" port, wired to real view
       fields. Verified via the preview-loop screenshot (matches the approved look).
    6. `render/charts.py` restyled WHITE (blue #3a6ea5 trend, mono ticks, no
       chart-junk); each Chart carries a one-line `summary` used as the img alt so a
       blocked image still reads. Index bar is now inline HTML, not a PNG.
    7. `render/send.py` rebuilt to the Outlook-reliable MIME tree
       multipart/related[ multipart/alternative[text,html], image, image ] — images
       are SIBLINGS of the alternative, inline + angle-bracketed Content-ID. Tree
       shape asserted in test_send_inline. NOTE: only a real Outlook send proves it
       renders — that is the human's test send.
    8. `brief.py` _build_view/_build_charts/_build_html/_brief_lines wired to the new
       view fields (sources, text_rows, directions, hbars, sparklines, per-section
       PNG charts keyed by section).
  Preview loop (headless-Chrome screenshot of the rendered template) was used to
  verify the look before shipping; no email send was needed per change.
- **STILL HUMAN (Track A) for the redesign:** one real Outlook test send to confirm
  (a) the new look renders in Outlook, (b) the CID charts show (the broken-box fix),
  (c) favicons degrade to clean text not broken glyphs. allow_repeat_send is still
  true so a manual dispatch will actually send.
- **POST-FIRST-SEND FIXES (2026-06-18, after human shared Outlook screenshots):**
  The first real redesigned send rendered correctly in Outlook (white look, CID
  charts NOT broken, favicon-as-text clean) but revealed three issues, now fixed
  on build/phases (182 tests green, +10):
  1. NARRATIVE DEGRADE (the banner + all-templated prose): the committed
     runs/2026-06-18.json showed raw_model_output={"per_section": {<real sections>}}
     — the model echoed the schema's literal "per_section" wrapper, so generate()
     keyed parsed.get(section_id) to None for every section and fell back to
     templates. FIX: narrative._unwrap_sections peels a per_section/sections/output
     envelope before keying by section id, AND the system prompt now explicitly says
     the top-level object is keyed BY SECTION ID, do not wrap in "per_section". This
     turns the next real send from fully-templated into real model prose + citations.
  2. WEEK/MONTH TIME-CONTEXT (human asked for past-week/month/etc): new
     engine/context.py computes trailing week (5-session) + month (21-session) change
     per metric from rolling history (bps for yields, pct otherwise). Surfaced three
     ways: the computed fallback line ("...up 1.8% on the week and 4.0% on the
     month..."), the At-a-Glance "why" tag (was a redundant "Higher on the session"),
     and added to the model's per-section input numbers as {key}_week_change /
     {key}_month_change so prose may cite them (validator accepts them, spec §6.2).
     Scope = week + month only (we already keep ~25 closes; YTD/1yr would need a much
     bigger committed state file — deferred).
  3. CHARTS LOOKED WEIRD: (a) WTI was drawing the whole 25-session backfill (108->75,
     a 34% span) labeled "1-month" — now clamped to the trailing 21 sessions so it
     reads as a real month (95->75). (b) The inline index bars were near-flat daily
     %-changes redundant with the glance — switched to WEEK %-change (heading "Index
     change, week"). (c) Added charts._pad_ylim to stop matplotlib magnifying a tiny
     real yield range into a sawtooth (the 10Y day-to-day noise over a month is real,
     so it stays truthful; padding only kicks in when the range is below ~1% of level).
  New files: engine/context.py, tests/test_context.py. NOTE: charts + real prose only
  populate fully on a non-degraded run with committed history; the next real send is
  where the human confirms the narrative un-degrade landed.
- **CHART OVERHAUL + DATED AXIS (2026-06-18):** Human said the charts "look weird,"
  have no axis labels/explanation, and asked for interactive/expandable charts.
  Interactive-in-email is IMPOSSIBLE (Outlook strips JS/iframes/web components), so
  the agreed answer: best-quality static charts that CLICK THROUGH to the live,
  zoomable Yahoo/FRED page. Shipped on build/phases (188 tests green, +6):
  1. STATE SCHEMA BUMP (backward compatible): each metric gains history_dates[]
     parallel to history[]. save_state trims both in lockstep; _commit_state stamps
     today's ISO date per appended close; backfill seeds approximate dates via the
     NYSE calendar (pandas-market-calendars, already pinned) so the x-axis is dated
     IMMEDIATELY. Old state files without history_dates still load (returns []).
     The dated axis is "good now" (one-time calendar seed for old points) and 100%
     real stored dates within ~a month as seeded points age out. last_run.json now
     carries a history_dates list per metric.
  2. charts.py overhaul: every PNG chart now has a left-aligned title, a grey
     "what it shows" subtitle (e.g. "Front-month futures, daily close · May 20 -
     Jun 18"), a DATED x-axis (real dates, ~4 ticks), a unit-labeled y-axis
     (USD/barrel, Yield %), and annotated start/end values. WTI clamped to the
     trailing 21 sessions; yield curve shows the 2s10s spread.
  3. CLICKABLE: the chart <img> is wrapped in an <a> to the live interactive page
     (FRED DGS10 / Yahoo CL=F chart); caption reads "Source: ... · View live
     interactive chart ->". This is the "expand in/out" experience the human wanted,
     delivered via click-through since email can't host an interactive chart.
  New files: none (engine/sessions.py was started then removed as over-engineered;
  date seeding lives in state.py). preview_fixture.py now inlines the real WTI chart
  as a data-URI so the browser preview shows the actual chart (cid: only resolves in
  an email client). Decision trail: interactive charts in email are not possible;
  YTD/1-year context deferred (would need a much larger committed state file).
- **100%-ACCURATE-STATS ARCHITECTURE (2026-06-18):** The 2nd real send was STILL
  degraded. Diagnosed from the committed runs/2026-06-18.json: (1) the per_section
  unwrap WORKED (real section keys), but (2) every section failed VALIDATION because
  the model stated week/month %-moves that were flat-out WRONG (said VIX -9% when
  actual was -1.7%; WTI -1.3% when actually +2.5%) and (3) inline citations like
  "WSJ (wsj-39)" leaked their trailing digit ("39") into the number check. The
  validator was correctly rejecting wrong numbers -> degrade. Human's standard:
  "everything saying stats must be 100% accurate." Fix = make accuracy STRUCTURAL
  (spec §1, "numbers computed in Python"):
    * The model now writes ONLY a number-free CAUSE clause (the sourced "why") +
      cause_source_id + confidence. The OUTPUT_SCHEMA and SYSTEM_PROMPT were
      rewritten: "Write NO NUMBERS AT ALL in your cause text; a single number
      discards the section." _accept_section now validates the CAUSE (must be
      number-free + source-tagged), and SectionResult.prose holds that cause clause.
    * Python writes EVERY figure: render/templated.numbers_sentence builds the
      accurate level + day + week + month + range sentence from the data;
      section_with_cause(field, history, cause) = that sentence + the model's cause.
      brief._brief_lines joins them. A wrong stat is now impossible by construction.
    * Validator hardened: _SOURCE_ID_RE strips "wsj-39"/"cnbc-11"/"fed-2" and
      _YEAR_RE strips bare years before number extraction (they are not market
      figures). Proven on the real run: 3/5 sections that had degraded now pass with
      the OLD model output; the 2 that still failed had a stray number in the cause
      ($60 gas, "50%" Kalshi) which the new number-free prompt forbids -> all 5
      expected to pass on the next send.
  192 tests green on py3.12. The next real send is the proof point: expect NO
  degraded banner and real sourced "why" prose with 100%-accurate Python numbers.
- **DEGRADED-BANNER FALSE ALARM FIXED — part (A) (2026-06-18):** The red "Degraded
  run" banner kept appearing on otherwise-clean runs because `brief.py` flipped the
  whole-brief banner on an OPTIONAL-calendar failure (`degraded = report.degraded or
  cal.degraded`). The "What to Watch" calendar (FMP primary, Finnhub backup) fails
  because FMP's free tier moved economic_calendar/earning_calendar to paid. Per spec
  §7.5 the banner is reserved for stale CORE data or a failed model only. Shipped on
  build/phases (198 tests green, +6):
    * brief.py: `degraded = report.degraded` (calendar no longer trips the banner).
      A failed optional calendar now sets `calendar_note` instead, an honest
      per-section caveat shown in "What to Watch" ("Scheduled-events feed unavailable
      this morning; check an economic calendar directly"), and prints a one-line run
      note. Core stale/missing data still trips the banner (unchanged).
    * render/viewmodel.py: BriefView gains `calendar_note` (default ""); `chart_cids`
      also got a default so the new field could precede it (all call sites use kwargs).
    * render/template.html.j2: renders `view.calendar_note` (italic, muted) under the
      What to Watch list when present.
    * sources/calendar.py: `_describe_error` surfaces the HTTP STATUS (e.g. "HTTP 402")
      from requests' HTTPError so the run log shows WHY the free tier failed; both
      providers log fetch/parse failures at WARNING (`logging.getLogger(__name__)`).
    * tests/test_calendar_note.py (new, 6 tests): calendar failure does NOT set
      view.degraded; clean calendar leaves no note; CORE failure still trips banner;
      _describe_error surfaces HTTP status; failed provider logs the reason.
- **FREE CALENDAR SOURCE WIRED — part (B) (2026-06-18):** Researched + verified free,
  cloud-reachable sources, then (with the human's approval) replaced FMP. Root problem
  confirmed: FMP moved economic_calendar/earning_calendar behind a paid plan. New wiring
  (199 tests green) — both optional, graceful-fail, never the tier-one trigger, never trip
  the banner:
    * ECONOMIC EVENTS -> FRED /releases/dates (the EXISTING FRED_API_KEY; gov-backed,
      rock-solid from datacenter IPs). New sources/fred.py::fetch_release_dates +
      ReleasesDatesFetcher type. include_release_dates_with_no_data=true is LOAD-BEARING
      (without it FRED omits upcoming dates). Response key is `release_dates`, rows carry
      release_id/release_name/date (verified against FRED's documented shape). calendar.py
      filters by a CURATED release-name substring set (_RELEASE_TIMES/_RELEASE_TITLES) so
      "What to Watch" stays signal-dense (CPI, PPI, NFP, PCE, GDP, Retail Sales, jobless
      claims, JOLTS, housing, etc.), de-dups by title, and attaches the canonical release
      clock time in CT (FRED gives DATE only). "Advance Monthly Sales for Retail and Food
      Services" is FRED's name for Retail Sales (handled).
    * EARNINGS -> Finnhub /calendar/earnings (EXISTING FINNHUB_API_KEY; earnings is on
      Finnhub's FREE tier — its economic calendar is premium, so we do NOT use that one).
      hour field gives bmo/amc directly.
    * fetch_calendar() rewritten: economic (FRED) and earnings (Finnhub) are INDEPENDENT —
      one can fail while the other succeeds; each contributes degraded=True only if its key
      was configured and it then failed. fmp_key param removed; releases_fetcher + fred_key
      added (both injectable for offline tests). FMP code + parsers deleted.
    * Endpoints verified to RESOLVE from this environment before wiring: FRED
      /releases/dates (clean 400 on bad key = reachable, param shape accepted), Finnhub
      /calendar/earnings (clean 401 = reachable, no cloud block). Nasdaq earnings backup
      was researched (works with a Mozilla UA) but SKIPPED per the human (cloud-IP 403 risk).
    * tests/test_calendar.py rewritten for the new architecture; test_calendar_note.py log
      assertions updated. NEWS: newsapi.org evaluated and REJECTED (free tier bans
      production use + 24h article delay); keeping free RSS for news.
    * Track A note: daily-brief.yml still passes FMP_API_KEY as a (now unused, harmless)
      env var; FRED_API_KEY + FINNHUB_API_KEY are both already set, which is all the new
      code needs. No workflow change required. The real-runner proof (does Finnhub earnings
      return data on the free tier; does FRED list today's releases) is the next real send.
- **VISUALS + MACRO OVERHAUL — DONE (2026-06-18), shipped to build/phases + mirrored
  to main (commit ae4b140), 226 tests green (+27).** The human asked for richer,
  more informative visuals and macro context. All Python-computed (accuracy stays
  structural; the model still writes ZERO numbers). What shipped:
  1. SECTION STAT TABLES: a small session/week/month table now renders at the TOP of
     each section box, before the prose. New `engine/stats.py` (pure: trailing change
     per metric in pct, or bps for rate-like series; em dash when history too thin).
     Surfaced via `viewmodel.SectionView.stat_table` + a `stat_table` macro in
     template.html.j2; built in `brief._build_view` from fields + state history.
  2. US EQUITIES: 4-row table (S&P/Nasdaq/Dow/Russell) x session/week/month, with the
     existing inline week %-change hbar KEPT below it (human wanted both).
  3. RATES CHART REWORK: dropped the confusing 2-panel curve. New
     `charts.ten_year_trend` = one clean padded 10Y month line (no sawtooth) + a
     Python-computed `ten_year_takeaway` ("what this tells you": level, week bps,
     range position). The 2s10s spread (a synthetic row, 10Y-2Y in bps) and DXY now
     read as NUMBERS in the rates stat table, not chart lines.
  4. COMMODITIES CHART: new `charts.commodities_normalized` = ONE chart with WTI,
     gold, AND copper rebased to 100 ~21 sessions ago (relative performance), legend
     + dashed 100 baseline, plus `commodities_takeaway` naming the leader/laggard.
  5. CHART TAKEAWAYS: every chart gets a Python-computed one-line read rendered under
     it ("What this tells you: ..."). No model numbers.
  6. NEW METRICS (all FREE, all OPTIONAL — they NEVER trip the degraded banner or the
     hard floor, which stay core-data/model only): COPPER (yfinance HG=F), and from
     FRED via the existing FRED_API_KEY: CPI YoY + PCE YoY (the `units=pc1` transform
     returns the YoY rate directly — no manual math, so 100% accurate by construction),
     FED FUNDS (DFF), HIGH-YIELD CREDIT SPREAD (BAMLH0A0HYM2). Wired through the metric
     registry (new `rate_like`/`optional`/`display` fields; `is_yield` now means
     "rate-like" = bps change for yields + the 4 macro rates), symbols.py (+`fred_units`),
     fred.py (units passthrough; `_call_fetcher` inspects the signature so a units
     transform is NEVER silently dropped — that would store a raw CPI index as a wrong
     number), prices.py (FRED-only metrics route to FRED, copper to yfinance), and the
     state schema (backward-compatible bump: `_commit_state` seeds any metric key not
     yet in an older last_run.json, so the macro metrics start accruing history on
     their first real send). Folded into the Rates and Commodities tables; copper also
     in the normalized commodities chart. No NEW sections added.
  New files: engine/stats.py, tests/test_stats.py, tests/test_macro_metrics.py.
  Verified via the preview-loop screenshot (matches the approved look). FRED series
  IDs (CPIAUCSL, PCEPI, DFF, BAMLH0A0HYM2) confirmed reachable; key-gated locally so
  the real-runner proof (do they return data on the next real send) is the next send.
  DEFERRED (not this session, per the human): the watchlist/movers per-stock
  session/week/month table + per-stock news + per-stock "why".

- **TEMPORARY flags to RESTORE before go-live (do not forget):**
  1. `config.yaml monitoring.allow_repeat_send: true` -> set back to **false**.
     It bypasses the once-per-day idempotency guard so we can do multiple test
     sends/day; while true the two DST crons CAN double-send.
- **Current phase:** Phase 7 (Email-safe template + charts) — BUILT + tested
  (142 tests green on py3.12). The last build phase. All seven phases are now
  built; only the Track A human go-live punch list remains (HANDOFF_PHASE7.md).
- **Build mode:** Human delegated autonomous build-out (2026-06-17): proceed
  through all phases, commit at each gate, hand off when context gets long.
  Track A (human-only) actions are being collected into a punch list for the end.
- **Next phase to build:** none — Phase 7 was the final build phase. Next steps
  are all Track A (secrets, watchlist, first real send, schedule watch).
- **Repo:** https://github.com/liessjake1-code/market-brief (public, `main` branch).
- **Local path:** /Users/jakeliess/market-brief
- **Today's date at setup:** 2026-06-17

---

## Done

### Environment / setup
- [x] Read all 5 docs in full (START_HERE, CLAUDE.md, spec, roadmap, execution guide).
- [x] Confirmed repo layout matches spec 8.1 (docs/ and data/ already correct;
      nothing needed moving). `.gitignore` reviewed and left as-is (it intentionally
      tracks last_run.json, runs/, config.yaml, data/*.yaml and ignores the Phase 0
      throwaway files).
- [x] Python 3.12.x confirmed locally (human).
- [x] `git init`, first commit, remote added, pushed to GitHub `main`.
      Commits so far: initial scaffold (8 files), then Phase 0 throwaway files.

### Track A (human) accounts/keys
- [x] GitHub repo created (empty, no README).
- [x] Brevo account created; single sender VERIFIED (sender = a Gmail address).
- [x] SMTP key generated.
- [ ] FRED / FMP / Finnhub / Anthropic API keys — NOT yet needed (Phase 2+/6).
- [ ] STATE_COMMIT_PAT (fine-grained PAT, contents:write this repo) — NOT yet
      needed (Phase 2).

### Decisions / config facts
- `EMAIL_FROM` = the verified Gmail sender.
- `EMAIL_TO` = jliess@tulane.edu (Tulane Microsoft 365 / Outlook inbox).
- Second price source: left provisionally "stooq" in config (Step 3). Revisit
  after Phase 0 runner-IP finding. So far NO Yahoo block observed (good sign that
  a second source may end up optional, but not yet confirmed over multiple days).

---

## Phase 0 — test send (status: manual run PROVEN, scheduled run pending)

### Files written (Track B) — THROWAWAY, delete after gate met
- `test_send.py` — 5 yfinance pulls (^GSPC, ^IXIC, ^DJI, ^RUT, ^TNX), plain HTML
  table, smtplib STARTTLS on 587, creds from env vars. Re-raises on send failure
  so a bad send shows as a red/failed Actions run.
- `.github/workflows/test-send.yml` — workflow_dispatch + two DST cron lines
  (13:30 and 14:30 UTC = 8:30 CT in CDT/CST). Installs only yfinance.
- NOTE: both are in `.gitignore`, so they were committed with `git add -f`.

### GitHub Secrets set by human (names only — values never recorded)
- [x] SMTP_HOST = smtp-relay.brevo.com
- [x] SMTP_USER (Brevo SMTP login)
- [x] SMTP_PASS (Brevo SMTP key)
- [x] EMAIL_FROM (verified Gmail)
- [x] EMAIL_TO = jliess@tulane.edu

### What happened on the manual run
- First manual run RED: `socket.gaierror [Errno -2] Name or service not known`
  on SMTP connect. Cause: SMTP_HOST secret value was wrong/empty. Human re-entered
  it as exactly `smtp-relay.brevo.com`.
- Second manual run GREEN. (Harmless warning: Node 20 deprecation on
  actions/checkout@v4 + setup-python@v5 — ignore for Phase 0; pin action versions
  when building the real daily-brief.yml.)
- Brevo logs showed "Delivered" + "Opened" (the "opened" is a security-scanner
  pixel fetch, not a real open). Message was DELIVERED to Tulane.
- Tulane QUARANTINED it. Human approved/released it and added the Gmail sender to
  Outlook Safe senders. This is the one-time deliverability trust step (spec 3.3).

### Phase 0 unknowns — 3 of 4 proven from the manual run
- [x] (a) free-relay email reaches the Tulane inbox after safe-senders.
- [x] (b) yfinance numbers render correctly from the runner.
- [x] (d) Yahoo did NOT block the cloud runner (no NO DATA / ERROR / NaN).
- [ ] (c) scheduler fires near 8:25-9:15 CT — STILL TO PROVE. Requires letting the
      cron fire on its own over ~2-3 weekday mornings. Cannot be proven by manual
      dispatch.

### Phase 0 gate (not yet fully met)
> A real Brevo email reliably reached the Outlook inbox ON A SCHEDULE, with correct
> numbers, from the cloud runner, and the runner-IP finding is recorded.
- Remaining: watch ~2-3 scheduled mornings, then record the runner-IP finding
  (so far: no block), then delete test_send.py and test-send.yml.

---

## Phase 1 — Safety net (status: BUILT, awaiting Actions verification)

### Files written (Track B)
- Deleted Phase 0 throwaways `test_send.py` + `.github/workflows/test-send.yml`
  and removed their (now obsolete) `.gitignore` entries.
- Repo layout per spec 8.1: `sources/` (prices, fred, calendar, news),
  `engine/` (state, diff, top_story, narrative), `render/` (charts,
  template.html.j2), `runs/.gitkeep`, package `__init__.py` files. All `.py`
  modules are docstring-only STUBS that name their implementing phase.
- `requirements.txt`: RESOLVED, mutually-compatible pins locked against Python
  3.12 via uv on 2026-06-17. Load-bearing: `yfinance==1.4.1`,
  `anthropic==0.109.2`. Also pandas 3.0.3, requests 2.34.2, matplotlib 3.11.0,
  feedparser 6.0.12, jinja2 3.1.6, python-dateutil 2.9.0.post0,
  pandas-market-calendars 5.4.0, pyyaml 6.0.3, pytest 9.1.0.
- `config.yaml`: spec 8.4 skeleton verbatim (number_tolerance_pct nested under
  narrative; second_price_provider "stooq" provisional; watchlist []).
- `brief.py`: argparse + `--no-send`. The no-state-on-no-send invariant is
  structural: all state writes funnel through `_commit_state()`, a hard no-op
  under `--no-send`. State logic itself is Phase 2.
- `tests/test_no_send_invariant.py`: regression test proving `--no-send` writes
  no `last_run.json` and never mutates an existing one. Passes locally.
- `.github/workflows/smoke-test.yml`: workflow_dispatch only; checkout@v4,
  setup-python@v5 (Python 3.12), pip install, `python brief.py --no-send`, pytest.

### Verified locally (Track B)
- `python brief.py --no-send` exits 0, writes no state file.
- Both invariant tests pass; all packages import; `config.yaml` validates against
  spec 8.4 with a real pyyaml parse on Python 3.12 (via uv).

### Phase 1 gate (MET — runner-side closed 2026-06-18)
> `smoke-test.yml` builds without sending on Actions; `--no-send` writes no state.
- Local half proven. HUMAN triggered `smoke-test.yml` on `build/phases` on
  2026-06-18: GREEN. Offline `--no-send` build ran clean and the full pytest suite
  passed on the 3.12 runner. This closes the runner-side verification gate for ALL
  seven build phases at once (Phases 1-7), since the smoke test builds + tests the
  whole codebase. NOTE: local interpreter is Python 3.14.6 (no 3.12 locally); pins
  were resolved against 3.12, which is what the runner uses, so the runner was the
  real gate, and it is now green.

---

## Phase 7 — Email-safe template + charts (status: BUILT + tested, 142 green)

The final build phase. Phases 2-6 are recorded in HANDOFF_PHASE7.md and the commit
history; this entry covers the last phase.

### Files written (Track B)
- `render/template.html.j2` — the real editorial template (was a placeholder).
  Single-column table layout, fully inline styles, web-safe fonts (Georgia
  masthead; `Consolas,'SFMono-Regular',monospace` figures). Spec §6.5 palette
  exactly (navy #13202E, paper #FBFAF7, gold #B0892F, green/red direction only).
  Diff line at top, At a Glance 10-row table (the one live "This morning" row
  labeled by pull time), floating Top Story then fixed fallback order, all eleven
  sections (honest one-liner when quiet), fenced + tinted "This morning so far"
  zone, What to Watch Today, degraded banner, source hyperlinks, favicons confined
  to Movers/Watchlist.
- `render/viewmodel.py` — assembles a validated BriefView from engine outputs so
  the template stays logic-light and unit-testable. Builds glance rows, orders the
  eleven sections per the Top Story decision, honest fallbacks for empty sections.
- `render/html.py` — Jinja env + render seam (autoescape on).
- `render/source_links.py` — every figure links to its source (yields→FRED series,
  everything else→Yahoo quote); Google s2 favicons, graceful fail.
- `render/charts.py` — matplotlib (Agg) → PNG → inline CID. Three default-on
  charts (index %-change bar, yield curve + 10Y trend, WTI 1-month); others behind
  the config `charts` flags. Each returns None on thin data and is skipped.
- `sources/calendar.py` — FMP primary, Finnhub backup, minor events + earnings
  for What to Watch / Earnings on Deck ONLY (never the tier-one trigger). Degrades
  quietly: no key → empty + not-degraded; configured-but-failed → degraded.
- `render/send.py` — extended `build_message`/`send` for multipart/related inline
  CID images (HTML-only path unchanged).
- `brief.py` — replaced `_render_templated_html` with viewmodel→Jinja render.
  Charts + render wrapped in crash barriers: a matplotlib failure ships a
  chart-free degraded brief; a render failure falls back to flat HTML (spec §5.6,
  the brief never blocks). Pre-market labeling wired via `schedule.premarket_label`
  by actual pull time. Offline seam + no-state-on-no-send invariant preserved; a
  no-send build writes a gitignored `brief.preview.html` for inspection.

### Tests (Track B)
- `tests/test_template_render.py`, `test_viewmodel.py`, `test_charts.py`,
  `test_calendar.py`, `test_source_links.py`, `test_send_inline.py`,
  `test_render_degrade.py`. 36 new tests; full suite 142 green on py3.12.

### Verified locally (Track B)
- `MARKET_BRIEF_OFFLINE=1 python brief.py --no-send` renders all three zones,
  writes no state, writes the preview file. Time-aware label flips Pre-market →
  Early session correctly. Charts produce valid PNG bytes; favicons confined to
  Movers/Watchlist (0 in At a Glance); yields link to FRED, oil to Yahoo. Both
  crash barriers verified to degrade, not crash.

### Phase 7 gate (Track B half met; real-send half is Track A)
> Brief renders across settled/live/forward zones; figures link to sources; live
> zone fenced + timestamped by actual pull time; charts embed as inline images.
- All met in the offline render. The real-send confirmation (numbers audit against
  source pages, inbox delivery) is the Track A first-send step.

### Note: daily-brief.yml already final
- Both DST crons, PAT checkout, workflow_dispatch, and all env secrets (incl.
  FMP_API_KEY / FINNHUB_API_KEY for the calendar) were already in place from
  Phase 5. No workflow change needed for Phase 7.

---

## Go-live punch list (Track A, post-build)

### 1. Runner-side gate — DONE (2026-06-18)
- `smoke-test.yml` GREEN on `build/phases`. Offline build + full pytest on the
  3.12 runner. Closes the runner-side verification for all 7 build phases.

### 2. Go-live secrets — DONE (2026-06-18)
- All secrets the workflow reads are now set (names only, values never recorded):
  STATE_COMMIT_PAT, ANTHROPIC_API_KEY, FRED_API_KEY, FMP_API_KEY, FINNHUB_API_KEY
  (set, though optional), plus the Phase 0 SMTP_HOST/USER/PASS + EMAIL_FROM/TO.
- TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID intentionally absent: heartbeat_channel
  is "github", so the workflow's empty Telegram env vars are harmless.
- STATE_COMMIT_PAT: fine-grained PAT, this repo only, Contents read+write,
  90-day expiry. ROTATE before expiry (set a quarterly reminder) — when it lapses
  the daily state commit-back silently fails.
- Verified the set against `.github/workflows/daily-brief.yml`: complete, no gaps.

### 3. Real watchlist in config.yaml — DONE (2026-06-18)
- watchlist = [SPCX, QUBT, TSLA, NVDA]. All four verified live on yfinance from
  the 3.12 env (5-day pulls OK). Note: SPCX is SpaceX common stock — it IPO'd on
  Nasdaq 2026-06-12, so it is a real tradable symbol, not a fund/proxy.
- ticker_domains favicons added: SPCX->spacex.com, QUBT->quantumcomputinginc.com,
  TSLA->tesla.com (NVDA->nvidia.com already present). Favicon is graceful-fail, so
  a wrong domain only drops the glyph; the row still reads from text.

### 4. First real production send — SENT (2026-06-18), audit pending
- Blocker found + fixed first: daily-brief.yml lived only on build/phases, but
  GitHub registers schedule/dispatch triggers from the DEFAULT branch (main).
  Merged build/phases -> main (human waived the no-push-to-main rule this once;
  15 add/add conflicts all resolved to the build/phases version, tree verified
  byte-identical, 142 tests green). "Daily Market Brief" then appeared in Actions.
- First manual send: GREEN. Log: FULL RUN, health missing_core=[] stale_core=[]
  degraded=False (clean data pull, no Yahoo block from the runner), send: sent
  (1 inline chart), schedule: after window (10:45 CT) sending late (correct
  relabel for a mid-day manual dispatch). Crons are now LIVE on main.
- NARRATIVE degraded=True: model ran but output fell back to templated lines.
  Could not audit why because the runs/ JSON dump was written only to the
  runner's ephemeral disk, never committed. FIXED: commit_state_back now stages
  runs/ dumps alongside last_run.json and commits when either changed (commit
  79c4f07 / merged to main cd1d12a; +2 tests, 144 green). Next send leaves an
  auditable runs/ dump in the repo.
- CONFIRMED: email landed in the Tulane INBOX (not Junk). Hardest external
  unknown cleared; Phase 0 safe-senders trust holds.
- DEGRADE ROOT CAUSE FOUND + FIXED: the committed runs/2026-06-18.json showed
  raw_model_output=null on every section (templated "No clear catalyst"). The
  API call SUCCEEDED (user was billed), so it was not auth/key/model-string. The
  model wrapped its JSON in a ```json fence, so json.loads() threw and _try_call
  swallowed it -> full degrade. Fixes shipped to main:
    (a) _try_call now LOGS the exception type+message (was silent) — commit on
        main 7a1e133. A silently degrading model is the spec §13 hard-to-notice
        failure.
    (b) _extract_json strips a code fence / preamble before json.loads, so
        fenced replies parse — commit on main ace9535, +4 tests.
  Expected: next send produces real causal prose instead of templated lines.
- IDEMPOTENCY GUARD (not a bug): a later green run sent no email because
  last_sent_date was already today -> "already sent (idempotent)". To allow
  multiple test sends/day while iterating, added TEMPORARY
  monitoring.allow_repeat_send (main dd5953a). MUST set back to false at go-live.
- STILL TODO: prove the prose fix on a real send (allow_repeat_send is now true,
  so a new manual dispatch will actually send today); audit numbers vs sources;
  then the LOOK/DESIGN pass on render/template.html.j2 (user dislikes current
  appearance) — likely its own focused session.
- NOTE (not a bug): first run printed "state-commit: no change to last_run.json"
  because there was no committed state baseline yet; normal commits begin next run.

### 5. Watch 2-3 scheduled mornings — TODO
- Prove cron timing (Phase 0 unknown c). Record runner-IP finding. Decide second
  price source (Decision 18; currently `second_price_provider: stooq`).

### 6. Confirm heartbeat on a simulated miss — TODO
- Dead-man's switch fires within a day on the independent (github) channel.

---

## Next actions

### Human (Track A)
- Verify Phase 1: trigger `smoke-test.yml` (Actions tab, "Run workflow"). Confirm
  green. No secrets needed for the smoke test. Then give the Phase 2 go-ahead.

### Human (Track A) — carried from Phase 0
1. Let the cron fire over the next ~2-3 weekday mornings; confirm mail arrives near
   8:30 CT in the inbox with live-looking numbers.
2. Record the runner-IP finding (block or no block) — decides whether the second
   price source is mandatory in Phase 5.
3. When watching is irrelevant to you / you want to move faster, you can also just
   accept the 3 proven unknowns and proceed, then keep an eye on real scheduled
   sends during Phase 5's "several mornings" step.

### Claude Code (Track B) — when given the go-ahead
- Delete `test_send.py` and `.github/workflows/test-send.yml` (Phase 0 cleanup).
- Begin Phase 1 (Safety net): repo layout per spec 8.1, requirements.txt with
  RESOLVED exact pins (yfinance + anthropic load-bearing), config.yaml skeleton
  exactly per spec 8.4, brief.py with argparse + --no-send implying NO state write,
  smoke-test.yml. Use plan mode; wait for approval before writing code.
- One phase per session. Verify each "Done when" gate before moving on.

---

## Operating reminders (carried across sessions)
- The model NEVER invents/alters a number; numbers computed in Python.
- Every causal claim traces to a cause_source_id or is hedged; "no clear catalyst"
  is a correct output.
- Settled facts vs live pre-market snapshot are fenced apart.
- Professional tone: no em dashes, no emojis, plain declarative prose.
- `--no-send` MUST imply no state write.
- Secrets only via env/GitHub Secrets, never hardcoded.
- data/tier_one_calendar.yaml and data/mechanical_moves.yaml are already built and
  source-verified — USE as-is, do NOT overwrite.
- Use the pre-decided artifacts in execution guide Part 4 exactly (state schema,
  model prompt, matcher, validators, primers).
