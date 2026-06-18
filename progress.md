# Progress Log

A running record of build progress across Claude Code sessions. Track A = human
(external steps); Track B = Claude Code (the code). See `START_HERE.md` and
`docs/claude-code-execution-guide.md` for the full two-track split.

This file is committed to the repo. NEVER put secret values here, only the names
of secrets and whether they are set.

---

## Status at a glance

- **GO-LIVE IN PROGRESS (2026-06-18):** All 7 phases built + merged to `main`
  (default branch, so the daily-brief.yml crons register and fire). Real sends
  land in the Tulane inbox. Now iterating on look + content quality before
  locking down. 149 tests green on py3.12.
- **EMAIL REDESIGN IN PROGRESS (2026-06-18):** Human disliked the look; approved a
  full redesign via visual previews -> see **HANDOFF_DESIGN.md** for all locked
  decisions. New look is "The Tape" on WHITE (serif masthead/headings, IBM Plex
  Mono numbers, inline hybrid charts, clickable per-section source citations).
  Item 1 of 9 DONE + shipped: `narrative.SectionResult.cited_sources` resolves the
  matched article {title,url} from the validated cause_source_id (commit 14def7b ->
  main 764fd8d). Items 2-9 (rich computed fallback, WSJ/FT free feeds, viewmodel
  threading, template port, hybrid charts, Outlook CID fix, tests) are pre-decided
  in HANDOFF_DESIGN.md for a fresh chat. Preview loop (headless-Chrome screenshot of
  the rendered template) is the iteration tool — no email send needed per change.
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
