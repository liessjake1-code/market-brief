# Progress Log

A running record of build progress across Claude Code sessions. Track A = human
(external steps); Track B = Claude Code (the code). See `START_HERE.md` and
`docs/claude-code-execution-guide.md` for the full two-track split.

This file is committed to the repo. NEVER put secret values here, only the names
of secrets and whether they are set.

---

## Status at a glance

- **Current phase:** Phase 6 (Explanation engine) — BUILT + tested (106
  tests green on py3.12). Validator built first; anthropic 0.109.2 call shape verified. Phase 1 also BUILT; both await one human Actions
  trigger of `smoke-test.yml` to close their gates on the runner.
- **Build mode:** Human delegated autonomous build-out (2026-06-17): proceed
  through all phases, commit at each gate, hand off when context gets long.
  Track A (human-only) actions are being collected into a punch list for the end.
- **Next phase to build:** Phase 7 (Email-safe template + charts) — the last
  build phase.
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

### Phase 1 gate (awaiting HUMAN)
> `smoke-test.yml` builds without sending on Actions; `--no-send` writes no state.
- Local half proven. Remaining: HUMAN triggers `smoke-test.yml` in the Actions
  tab and confirms it runs green on the 3.12 runner. NOTE: local interpreter is
  Python 3.14.6 (no 3.12 locally); pins were resolved against 3.12, which is what
  the runner uses, so the runner is the real gate.

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
