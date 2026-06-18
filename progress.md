# Progress Log

A running record of build progress across Claude Code sessions. Track A = human
(external steps); Track B = Claude Code (the code). See `START_HERE.md` and
`docs/claude-code-execution-guide.md` for the full two-track split.

This file is committed to the repo. NEVER put secret values here, only the names
of secrets and whether they are set.

---

## Status at a glance

- **Current phase:** Phase 1 (Safety net) — DONE and validated (2026-06-17).
  Built from the single-file HANDOFF and merged into this repo, keeping the
  existing docs/, CLAUDE.md, .gitignore, and the populated data/*.yaml.
- **Next phase to build:** Phase 2 (State caching + first-run backfill) — NOT
  started.
- **Repo:** https://github.com/liessjake1-code/market-brief (public, `main` branch).
- **Local path:** /Users/jakeliess/market-brief (this repo);
  also /Users/jakeliess/market-briefv2 (the single-file HANDOFF working copy).
- **Today's date at setup:** 2026-06-17

---

## Done

### Track B (Claude Code) — Phase 1: Safety net (2026-06-17)
- [x] Pinned the two load-bearing deps in `requirements.txt`:
      `yfinance==1.4.1`, `anthropic==0.109.2` (resolved from PyPI at build time).
- [x] `config.yaml` created with the spec toggles; secrets stay in env only.
- [x] `brief.py` entry point with `--no-send` => NO state write wired in from
      the start (`write_state = not args.no_send`, decided once). The no-send
      preview output uses a gitignored name.
- [x] `.github/workflows/smoke-test.yml` (build-without-send on
      `workflow_dispatch`; read-only data keys only, no SMTP secrets on it).
- [x] Phase-tagged stub modules for every later-phase file (sources/, engine/,
      render/) — each raises NotImplementedError so nothing fakes data.
- [x] Validated: config loads, `--no-send`=>write_state False / default=>True,
      `brief.py --no-send` reaches the pipeline and stops with the explicit
      "not built yet" error (no crash, no fake data).
- [x] Kept the existing populated `data/*.yaml` and the thorough `.gitignore`;
      did NOT overwrite them with the single-file HANDOFF's empty placeholders.

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

## Next actions

### Human (Track A)
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
