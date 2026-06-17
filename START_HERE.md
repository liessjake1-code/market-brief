# START HERE

This is your ordered, human-only entry point for building the Daily Market Brief.
It collects every step that **only you** can do (Track A in the execution guide)
into one sequence. Claude Code (Track B) does all the code, phase by phase, from
the three design docs already in this repo.

The rule of thumb: if a step here is waiting on Claude Code, you are confused.
Everything in this file is your job, by hand, outside the chat.

## How the pieces fit

1. Drop this whole package into an (empty) GitHub repo in this layout:
   `START_HERE.md` (this file), `CLAUDE.md`, and `.gitignore` at the root;
   the three design docs (`daily_market_brief_SPEC.md`, `market-brief-roadmap.md`,
   `claude-code-execution-guide.md`) in a `docs/` folder; and
   `tier_one_calendar.yaml` + `mechanical_moves.yaml` in a `data/` folder.
   (See the full map at the bottom of this file. CLAUDE.md expects the design
   docs under `docs/`.)
2. Work this file top to bottom. It interleaves the human steps with the points
   where you hand a phase to Claude Code.
3. For each build phase, open the execution guide (Part 5), paste that phase's
   prompt into a fresh Claude Code session, approve its plan, then verify the
   phase's "Done when" gate before moving on. One phase per session.

The full design lives in the spec; the phase order in the roadmap; the runbook
and the pre-decided artifacts (state schema, model prompt, validators, primers)
in the execution guide Part 4. Claude Code must use those exactly, not invent its
own.

---

## Boot Claude Code (paste this once Steps 1-2 are done and the repo is open)

Claude Code runs inside the repo, so you must first create the repo, drop in the
files, install Claude Code, and authenticate it (Steps 1-2 below). Then open the
repo in VS Code (or your terminal) with Claude Code running and paste this:

> Read `START_HERE.md`, `CLAUDE.md`, and all three docs in `docs/` in full before
> doing anything. Then:
> 1. Confirm you understand the two-track split: you build the code (Track B); I
>    do every external step myself (accounts, API keys, GitHub Secrets, the PAT,
>    running workflows in the Actions tab, watching the Phase 0 mornings, the
>    Outlook safe-senders fix). Never claim to have done a step that is mine.
> 2. Check the repo against the layout in START_HERE and spec §8.1. If the three
>    design docs are at the root instead of `docs/`, move them into `docs/` and
>    confirm CLAUDE.md's paths resolve. Confirm `data/tier_one_calendar.yaml` and
>    `data/mechanical_moves.yaml` are present, and do NOT recreate or overwrite
>    them; they are already built and source-verified.
> 3. Then act as my guide using START_HERE as the checklist. Ask me which of
>    Steps 1-3 are already done, and tell me exactly what to do next for anything
>    outstanding, one step at a time.
> 4. When we reach Phase 0 (Step 4), write the throwaway `test_send.py` and
>    `.github/workflows/test-send.yml` exactly per execution guide Part 2.1 (under
>    ~40 lines of Python, two cron lines for DST). Then tell me precisely which
>    GitHub Secrets to set and where, and stop and hand back to me to run it on
>    Actions and watch the mornings.
>
> Do not write any Phase 1+ code yet. We stop after the Phase 0 gate is met. Wait
> for my go-ahead at each handoff.

Keep that first session scoped to Phase 0. Start a fresh session for each later
phase, pasting that phase's prompt from execution guide Part 5.

---

## Step 1 — Install your local toolchain (execution guide 1.1)

- [ ] **Python 3.12** — `python3 --version`. Install from python.org if missing.
- [ ] **git** — `git --version`.
- [ ] **Node.js 18+** — only needed if you install Claude Code via npm (the native
      installer needs no Node). `node --version`; use `nvm` if missing, never `sudo npm`.
- [ ] **Claude Code** — native installer is recommended (no Node needed). See
      `https://docs.claude.com/en/docs/claude-code/overview`. On Windows, WSL2 is
      the smoother path. Verify with `claude --version` and `claude doctor`.
- [ ] **A Claude plan that includes Claude Code** — Pro, Max, Team, Enterprise, or
      a Console (API-billed) account. The free plan is rejected. First `claude`
      launch opens a browser to authenticate.

## Step 2 — Create accounts and collect keys (execution guide 1.2)

Open a scratch note. Treat every value as a password; never commit them. You will
paste these into GitHub Secrets in Step 8.

- [ ] **GitHub account + a new empty repo.** Choose **public** (unlimited Actions
      minutes, recommended) vs private. Do not add repo contents yet beyond this
      package.
- [ ] **Brevo account** (free email relay). Complete **single-sender verification**
      (no domain needed). Record: SMTP host `smtp-relay.brevo.com`, port 587, your
      SMTP login (username), and an SMTP/API key (password), plus the verified
      `From` address. Verify the current free-tier limits at signup.
- [ ] **FRED API key** — free: `https://fredaccount.stlouisfed.org/apikeys`.
- [ ] **FMP API key** — free tier, for the minor calendar/earnings only.
- [ ] **Finnhub API key** — optional FMP backup; skippable at launch.
- [ ] **Anthropic API key** — `https://console.anthropic.com`. This funds the one
      model call per weekday and is a separate spend from your Claude Code plan.
- [ ] **GitHub fine-grained PAT** — scope: contents write, this repo only. This is
      `STATE_COMMIT_PAT`, which keeps the scheduled workflow from being auto-disabled
      at 60 days.
- [ ] **(Optional) Telegram bot token + chat ID** — only if you want the heartbeat
      on Telegram instead of GitHub's built-in workflow-failure email.

## Step 3 — Make the one open decision (execution guide 1.3)

- [ ] **Second price source:** leave it provisionally as **Stooq** in `config.yaml`.
      You cannot truly decide until Phase 0 tells you whether the cloud runner gets
      blocked by Yahoo. Revisit after Phase 0.

## Step 4 — Phase 0: the test send (execution guide Part 2)

This phase is almost entirely yours. Its value is real mornings on a real
schedule, which only you can run and watch. Do not let Claude Code "finish" Phase 0
by writing code.

- [ ] In a fresh Claude Code session, have it write the throwaway `test_send.py`
      and `test-send.yml` (prompt in execution guide 2.1). Commit and push.
- [ ] **Set the minimum secrets** in the repo (Settings -> Secrets and variables ->
      Actions): `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`
      (your Outlook address). Claude Code cannot do this.
- [ ] **Trigger `test-send.yml` from the Actions tab** (workflow_dispatch). It must
      run on Actions, not locally; only the cloud runner reveals runner-IP blocking
      and scheduler timing.
- [ ] **First-land junk fix:** when the first mail hits Junk, mark it **not junk**
      and add the sender to Outlook **Safe senders** (Settings -> Junk email ->
      Safe senders).
- [ ] **Watch ~3 mornings** and confirm: (a) mail lands in inbox after safe-senders,
      (b) yfinance numbers match a live source at send time, (c) the scheduler fires
      inside ~8:25-9:15 CT, (d) Yahoo does not block the runner (no NaN/empty pulls).
- [ ] **Record the runner-IP finding** — it decides whether the second price source
      is mandatory in Phase 5.3. Then delete `test_send.py` and `test-send.yml`.

> **GATE:** a real Brevo email reliably reached your Outlook inbox on a schedule,
> with correct numbers, from the cloud runner, and you know whether the runner
> gets blocked. Do not proceed until this is true.

## Step 5 — Confirm the repo foundation (execution guide Part 3)

- [ ] The three design docs and `CLAUDE.md` are committed in the repo (this package
      already includes them). They are Claude Code's source of truth and must be
      in-repo so every session can read them.
- [ ] For each phase: fresh `claude` session, paste the phase prompt, use plan mode,
      approve, let it implement, verify the gate, commit. Do not run fully autonomous
      on the first build.

## Step 6 — Hand Phases 1 through 7 to Claude Code (execution guide Part 5)

Run these one session each, verifying each "Done when" gate (gates are in the
roadmap and execution guide Part 5):

- [ ] **Phase 1 — Safety net** (pins, config skeleton, `--no-send` writes no state,
      smoke-test workflow). *You* trigger `smoke-test.yml` on Actions to verify.
- [ ] **Phase 2 — State caching + first-run backfill.** *You* set `STATE_COMMIT_PAT`
      as a secret for the commit-back to work.
- [ ] **Phase 3 — Diff line.**
- [ ] **Phase 4 — Top Story engine + the two YAML files.** The YAMLs are already in
      `data/` in this package (built and source-verified 2026-06-17). **Your job:**
      re-verify them before relying on them and refresh quarterly. See Step 7.
- [ ] **Phase 5 — Resilience and data layer.** Then run the real pipeline on Actions
      for **several mornings with templated why lines** (no model prose yet) to shake
      out data, delivery, and timing bugs.
- [ ] **Phase 6 — Explanation engine.** Build the tolerant number validator FIRST.
      Audit a few `runs/` JSON dumps by eye.
- [ ] **Phase 7 — Email-safe template and charts.** Build last.

## Step 7 — Verify the tier-one and mechanical-move YAMLs (execution guide Phase 4 data entry)

These two files are the most consequential triggers in the system, so the dates
are yours to own even though they are pre-filled and source-verified.

- [ ] Spot-check `data/tier_one_calendar.yaml` against the agency URLs in its header
      (federalreserve.gov, bls.gov, bea.gov).
- [ ] Spot-check `data/mechanical_moves.yaml` against the FTSE Russell schedule and
      an options-expiration calendar.
- [ ] **Two findings already flagged in the files, confirm you are comfortable with
      them:** the Jan-data jobs report is **Feb 11** per official BLS (not Feb 6 as
      in earlier research), and June witching is **Thu Jun 18** because Jun 19 is
      Juneteenth (markets closed). A couple of shutdown-disrupted H1 PCE/GDP dates
      carry `# VERIFY` markers.
- [ ] Set a quarterly calendar reminder to re-verify both files.

## Step 8 — Go-live (execution guide Part 6)

- [ ] **Confirm ALL secrets are set** in the repo: `ANTHROPIC_API_KEY`,
      `FRED_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY` (if used), `SMTP_HOST`,
      `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`, `STATE_COMMIT_PAT`, and
      the Telegram secrets if the heartbeat uses them.
- [ ] **Populate a real `watchlist`** in `config.yaml` before the first send. An
      empty watchlist is the most-skipped block in the brief.
- [ ] **First real production send:** trigger `daily-brief.yml` via workflow_dispatch.
      If it junks, repeat the safe-senders step. Then **audit the brief against the
      source pages** — this is your first real worked example.
- [ ] **Let the schedule take over.** Once a manual run is clean, the two cron lines
      handle the daily send. **Confirm the heartbeat fires** if you simulate a miss,
      so you know the dead-man's switch works.

> **DONE when:** a real brief lands in your inbox on the daily schedule, every
> number audits against its source page, the live zone is fenced and timestamped,
> and a simulated stoppage reaches you within a day on the independent channel.

---

## The human-only punch list (execution guide Part 7)

Everything Claude Code cannot do. If you are stuck waiting on it for one of these,
stop. It is your job.

- [ ] Install Python, git, Node (if npm), Claude Code; authenticate Claude Code.
- [ ] Create GitHub repo (public vs private).
- [ ] Create Brevo account; verify single sender; collect SMTP creds.
- [ ] Get FRED, FMP, (Finnhub), Anthropic API keys.
- [ ] Create the fine-grained PAT (`STATE_COMMIT_PAT`).
- [ ] (Optional) Create Telegram bot + chat ID.
- [ ] Set ALL of the above as GitHub Secrets.
- [ ] Run the Phase 0 test send on Actions; watch three mornings; do safe-senders.
- [ ] Record the runner-IP finding; decide the second price source.
- [ ] Verify `tier_one_calendar.yaml` and `mechanical_moves.yaml` against official
      schedules; set a quarterly refresh reminder.
- [ ] Run Phase 5 several mornings with templated lines before adding the model.
- [ ] Populate a real watchlist before first send.
- [ ] Trigger the first real send; audit against sources; confirm heartbeat works.
- [ ] Quarterly: bump yfinance + anthropic pins, confirm every secret authenticates,
      re-check the model string, prune `runs/`, re-verify the two YAMLs.

---

## Where each file goes (repo layout, spec Section 8.1)

```
market-brief/
  START_HERE.md                    <- this file (repo root)
  CLAUDE.md                        <- repo root (Claude Code reads at every session)
  .gitignore                       <- repo root
  docs/
    daily_market_brief_SPEC.md     <- design doc
    market-brief-roadmap.md        <- design doc
    claude-code-execution-guide.md <- design doc
  data/
    tier_one_calendar.yaml         <- included in this package (built + verified)
    mechanical_moves.yaml          <- included in this package (built + verified)
  ...                              <- everything else is built by Claude Code, Phases 1-7
```

This is the layout CLAUDE.md expects (design docs under `docs/`). If you ever move
the design docs to the repo root instead, update the three `docs/...` paths in
CLAUDE.md to match.
