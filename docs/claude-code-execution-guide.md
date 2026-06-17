# Daily Market Brief: Claude Code Execution Guide

**What this document is.** The spec (`daily_market_brief_SPEC.md`) describes *what* to build and *why*. The roadmap (`market-brief-roadmap.md`) describes the *order*. This third document is the *runbook*: the exact step-by-step path from a clean machine to a working brief landing in your inbox, with every step labeled as either **[HUMAN]** (only you can do it) or **[CC]** (hand to Claude Code), plus the pre-decided artifacts Claude Code would otherwise invent inconsistently.

**How to read it.** Work top to bottom. Do not skip the human prerequisites; Claude Code cannot do them and will stall or fake them if they are missing. Each phase ends with a **verification gate** you must pass before starting the next phase.

**The golden rule of driving Claude Code here:** one phase per session, verify the "Done when" bar, commit, then start a fresh session for the next phase. Long single sessions drift and lose the thread. Short phase-scoped sessions stay accurate.

---

## Part 0 — The mental model (read once, then act)

This build has two tracks running in parallel, and confusing them is the main way people get stuck.

**Track A — external reality (HUMAN only).** Creating accounts, copying API keys, setting GitHub Secrets, running the Phase 0 mornings on a real schedule, marking mail "not junk," populating your watchlist. Claude Code has no browser, no access to your GitHub settings, and cannot wait three mornings. Everything in this track is you, by hand.

**Track B — the code (CC builds, HUMAN verifies).** Every `.py` file, the Jinja template, the YAML config skeleton, the workflows, the validators. Claude Code writes all of it. You read its plan, approve, and verify the result against the spec.

The phases below interleave the two tracks on purpose, because that is the real order of operations. The label on each step tells you whose job it is.

A blunt truth about Phase 0: it is **almost entirely Track A**. Claude Code can write the throwaway test script, but the *value* of Phase 0 is the three mornings of real runs that only you can run and watch. Do not let Claude Code "complete" Phase 0 by writing code; Phase 0 is complete when real email has landed in your inbox on a schedule for three mornings.

---

## Part 1 — Human prerequisites (Track A, do all of this first)

None of this is Claude Code's job. Do it before you install Claude Code, because Phase 0 needs it.

### 1.1 Install the local toolchain [HUMAN]

You need these on your machine:

- **Python 3.12** — confirm with `python3 --version`. If missing, install from python.org or your OS package manager.
- **git** — confirm with `git --version`.
- **Node.js 18 or newer** — only required if you install Claude Code via npm (the native installer needs no Node). Confirm with `node --version`. Use `nvm` to install if missing; never `sudo npm`.
- **Claude Code itself.** The native installer is the currently recommended method and needs no Node.js:
  - macOS/Linux/WSL: run the official install command from the Claude Code docs (`https://docs.claude.com/en/docs/claude-code/overview`), then open a new terminal and run `claude --version`.
  - Windows: WSL2 is the smoother path; native PowerShell works but hits more friction. Git for Windows enables the Bash tool.
  - npm alternative: `npm install -g @anthropic-ai/claude-code` (Node 18+).
  - Verify with `claude doctor`, which checks install type, auth, and config.
- **A Claude plan that includes Claude Code** — Pro, Max, Team, Enterprise, or a Console (API-billed) account. The free plan is rejected. First `claude` launch opens a browser to authenticate.

### 1.2 Create accounts and collect keys [HUMAN]

Open a scratch note and collect these as you go. You will paste them into GitHub Secrets later (step 2.4). Treat every one as a password; never commit them.

- **GitHub account + a new repo.** Decide **public** (unlimited Actions minutes — recommended per spec §13) vs private. Do not create the repo contents yet; Claude Code scaffolds those. Just have the empty repo.
- **Brevo account** (the free email relay, spec §3.3). Complete **single-sender verification** — verify the one `From` address you will send from. No domain needed. Then collect: SMTP host (`smtp-relay.brevo.com`), port 587, your SMTP login (username), and an SMTP key / API key (password). Record the verified `From` address.
- **FRED API key** — free, from `https://fredaccount.stlouisfed.org/apikeys`.
- **FMP API key** — free tier, for the minor calendar/earnings only.
- **Finnhub API key** — optional, only if you want the FMP backup wired now. Skippable at launch.
- **Anthropic API key** — from the Console (`https://console.anthropic.com`). This funds the one model call per weekday. Note: this is a *separate* spend from your Claude Code plan; the brief calls the API directly.
- **A GitHub fine-grained Personal Access Token (PAT)** — scope: contents write, this repo only. This is `STATE_COMMIT_PAT`, used so the daily state commit counts as activity and the workflow is not auto-disabled at 60 days (spec §8.3).
- **(Optional) Telegram bot token + chat ID** — only if you want the heartbeat on Telegram rather than GitHub's built-in workflow-failure email (spec §7.6).

### 1.3 The one decision to make now [HUMAN]

**Second price source:** Stooq or Twelve Data or none. You cannot truly decide this until Phase 0 tells you whether the cloud runner gets blocked by Yahoo, so leave it provisionally as Stooq in config and revisit after Phase 0. (Spec Decision 18.)

---

## Part 2 — Phase 0: the test send (mostly Track A)

Goal: prove the four external unknowns before building anything smart — does free-relay mail reach your inbox, does yfinance give correct numbers from the runner, does the Actions schedule fire near 8:30, and **does Yahoo block the cloud-runner IP.**

### 2.1 [CC] Write the throwaway test script and workflow

Start Claude Code in your cloned (empty) repo and give it this prompt verbatim:

> We are at Phase 0 of a project specified in `daily_market_brief_SPEC.md` (I will paste it / it is in the repo). Write a single throwaway file `test_send.py` that: pulls about five numbers from yfinance (S&P `^GSPC`, Nasdaq `^IXIC`, Dow `^DJI`, Russell `^RUT`, and the 10-year `^TNX`), builds a minimal plain HTML table, and sends it via `smtplib` over STARTTLS on port 587 using env vars `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`. No error handling beyond printing failures. Then write `.github/workflows/test-send.yml` with `workflow_dispatch` and a temporary schedule near 8:30 AM Central (two cron lines, 13:30 and 14:30 UTC, to cover DST). Do not add any other files. Keep it under ~40 lines of Python.

Read its plan, approve, let it write the two files. Commit and push (Claude Code can do the git steps, or you do them).

### 2.2 [HUMAN] Set the minimum secrets

In the GitHub repo: Settings → Secrets and variables → Actions. Add: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`. (Your Outlook address is `EMAIL_TO`.) Claude Code cannot do this; it has no access to your repo settings.

### 2.3 [HUMAN] Run it on Actions, not locally

In the Actions tab, trigger `test-send.yml` via the `workflow_dispatch` button. **This must run on Actions** — a local run cannot reveal runner-IP blocking or scheduler timing, which are two of the four unknowns.

### 2.4 [HUMAN] First-land junk fix

When the first mail lands in Junk (expected, no custom domain), mark it **not junk** and add the sender to the Outlook **safe-senders** list: Settings → Junk email → Safe senders.

### 2.5 [HUMAN] Watch three mornings

Let the temp schedule fire for ~3 mornings and confirm each:
- (a) mail lands in inbox after safe-senders,
- (b) yfinance numbers match a live source at send time,
- (c) the scheduler fires inside ~8:25–9:15 CT,
- (d) **Yahoo does not block the runner** (no NaN/empty pulls from the cloud).

### 2.6 [HUMAN] Record the runner-IP finding and clean up

Write down whether the runner was ever blocked — it decides whether the second price source is mandatory (Phase 5.3 / spec Decision 18). Then have Claude Code delete `test_send.py` and `test-send.yml`, or delete them yourself.

> **VERIFICATION GATE — do not proceed until:** a real email from Brevo reliably reached your Outlook inbox on a schedule, with correct numbers, from the cloud runner, and you know whether the runner gets blocked.

---

## Part 3 — Set up Claude Code for the real build (Track B foundation)

### 3.1 [HUMAN] Put the three docs in the repo

Place `daily_market_brief_SPEC.md`, `market-brief-roadmap.md`, and this guide in the repo root (or a `/docs` folder). Commit them. They are Claude Code's source of truth and must be in-repo so every session can read them.

### 3.2 [HUMAN/CC] Create `CLAUDE.md`

Run `/init` inside Claude Code to bootstrap one, then replace its contents with the following (this is the persistent context Claude Code reads at the start of every session). Adjust paths if you used a `/docs` folder.

```markdown
# Project: Daily Market Brief

An automated weekday market brief, emailed at 8:30 AM Central via GitHub Actions.
It reports a finished, settled trading day plus a clearly fenced live pre-market
snapshot, with every number sourced and every "why" traced to real reporting.

## Source of truth (read these before any task)
- `daily_market_brief_SPEC.md` — the full design. This is authoritative.
- `market-brief-roadmap.md` — the phase order and "Done when" bars.
- `claude-code-execution-guide.md` — the runbook, including pre-decided artifacts
  (state schema, model prompt, matcher, validators, primers). Use these exactly;
  do not invent your own versions.

## Non-negotiable rules (from spec §1, §2, §5.6)
- The model NEVER invents or alters a number. Numbers are computed in Python.
- Every causal claim must trace to a supplied article (cause_source_id) or be hedged.
- "No clear catalyst" is a correct, encouraged output. Never manufacture a cause.
- Settled facts and live pre-market snapshots are visually and verbally fenced apart.
- Professional tone: no em dashes, no emojis, plain declarative prose.
- The brief never blocks on the model or news; it degrades to templated lines.

## Tech stack
- Python 3.12. Dependencies pinned in requirements.txt (yfinance and anthropic
  pins are load-bearing — see spec §8.2 / §13).
- yfinance (prices), FRED (rates + oil cross-check), RSS (news), Anthropic API (prose).
- Jinja2 email template, matplotlib charts (inline CID), GitHub Actions runner.

## Commands
- `python brief.py --no-send` — build only, writes HTML to disk, NO state write.
- `python brief.py` — full run, sends, writes state.
- Smoke test workflow: `smoke-test.yml` (build without send on workflow_dispatch).

## Critical conventions
- `--no-send` MUST imply no state write (never touch last_run.json or last_sent_date).
- Secrets come only from env vars / GitHub Secrets, never hardcoded.
- The state commit uses STATE_COMMIT_PAT and only happens on Actions, not locally.
- Build in the phase order in the roadmap. Do not jump ahead; later phases depend
  on earlier ones (e.g. nothing references "yesterday" before state caching exists).

## Workflow expectation
Work one roadmap phase at a time. Describe your plan and wait for approval before
writing code. After each phase, ensure the phase's "Done when" bar is met.
```

### 3.3 [HUMAN] Working style for every phase session

For each phase below: start a fresh `claude` session, paste the phase prompt, let it propose a plan, approve, let it implement, then run the verification yourself. Use plan mode and approve steps; do not let it run fully autonomous on the first build. Commit at the end of each phase so you always have a fallback.

---

## Part 4 — The pre-decided artifacts (hand these to Claude Code; do not let it invent them)

These are the decisions the roadmap leaves open. Putting them here, fixed, is what makes the build mechanical and consistent across sessions. When a phase prompt says "use the artifact from Part 4," this is what it means.

### 4.1 `last_run.json` schema (Phase 2)

```json
{
  "schema_version": 1,
  "last_sent_date": "2026-06-16",
  "sent_today": false,
  "run_timestamp_ct": "2026-06-16T08:31:00-05:00",
  "chosen_top_story": "rates_and_dollar",
  "metrics": {
    "sp500":   { "close": 5431.2, "prev_close": 5410.0, "change_pct": 0.39,
                 "history": [5388.1, 5402.7, 5410.0, 5431.2] },
    "nasdaq":  { "close": 17688.0, "prev_close": 17620.0, "change_pct": 0.39,
                 "history": [] },
    "dow":     { "close": 38900.0, "prev_close": 38850.0, "change_pct": 0.13,
                 "history": [] },
    "russell": { "close": 2022.0, "prev_close": 2030.0, "change_pct": -0.39,
                 "history": [] },
    "vix":     { "close": 13.1, "prev_close": 12.9, "change_pct": 1.55,
                 "history": [] },
    "wti":     { "close": 76.2, "prev_close": 78.5, "change_pct": -2.93,
                 "history": [] },
    "gold":    { "close": 2330.0, "prev_close": 2325.0, "change_pct": 0.22,
                 "history": [] },
    "dxy":     { "close": 104.6, "prev_close": 104.4, "change_pct": 0.19,
                 "history": [] },
    "ust10y":  { "close": 4.28, "prev_close": 4.20, "change_pct": null,
                 "change_bps": 8.0, "history": [] },
    "ust2y":   { "close": 4.71, "prev_close": 4.69, "change_bps": 2.0,
                 "history": [] },
    "btc":     { "close": 64000.0, "prev_close": 63200.0, "change_pct": 1.27,
                 "history": [] },
    "eth":     { "close": 3450.0, "prev_close": 3410.0, "change_pct": 1.17,
                 "history": [] }
  }
}
```

Rules for Claude Code: `history` is a list of recent daily closes (most recent last), long enough to serve 20-day high/low and streak counts (keep ~25 entries). Yields carry `change_bps` not `change_pct`. Keep the file human-readable (indented). Source each metric's history from the same source that is morning-primary for it (FRED for yields, yfinance for the rest) per spec §5.5.

### 4.2 The single model call — prompt structure (Phase 6)

The call sends one system prompt and one user message, and expects strict JSON back. Hand Claude Code this exact structure.

**System prompt (fixed):**

```
You are the writer for a daily market brief. You are given computed numbers and a
small set of news articles. You write short, grounded causal prose. You operate
under three hard rules:

1. You may NEVER state a number that is not in the provided inputs. Round and
   approximate ("about 76 dollars", never "76.23"). If a figure is not in the
   inputs, do not write it.
2. Every causal claim ("X fell because Y", "on soft demand", "after the data")
   must reference one of the supplied articles by its source_id. If no supplied
   article supports a cause, write "no clear catalyst" instead. Inventing a
   plausible cause is a failure; honest uncertainty is correct.
3. First EXTRACT the explicit causal claims reporters made (quote the reporter's
   reason and its source_id), THEN write each section using only those extracted
   reasons plus the provided numbers.

Output strict JSON only, no prose outside the JSON, matching the schema given in
the user message. One entry per section. For quiet sections with no move and no
matched article, set confidence low and write one honest line.
```

**User message (assembled per run, JSON):**

```json
{
  "sections": [
    {
      "section_id": "rates_and_dollar",
      "numbers": { "ust10y": 4.28, "ust10y_change_bps": 8,
                   "ust2y": 4.71, "spread_2s10s_bps": -43,
                   "ust10y_5d_high": 4.31, "ust10y_5d_low": 4.18,
                   "ust10y_streak": "3 sessions higher",
                   "ust10y_weekly_change_bps": 12 },
      "primer": "The 10-year yield is the main discount rate for equities; rising yields pressure long-duration tech.",
      "articles": [
        { "source_id": "a1", "title": "...", "summary": "...", "url": "...", "match_score": 0.82 },
        { "source_id": "a2", "title": "...", "summary": "...", "url": "...", "match_score": 0.31 }
      ]
    }
  ],
  "output_schema": {
    "per_section": { "level": "string", "change": "string", "context": "string",
                     "cause": "string", "cause_source_id": "string or null",
                     "confidence": "low|medium|high", "prose": "string" }
  }
}
```

Model: `claude-sonnet-4-6` (from config). Temperature low. The full set of numbers in `numbers` — including derived figures (weekly sums, the 2s10s spread, index-vs-index gaps) — is exactly the set the validator (4.4) checks against, so compute every figure you want the model allowed to cite (spec §5.6 step 1).

### 4.3 The matcher (Phase 6, step 3)

Deterministic, inspectable, no model. Hand Claude Code this design:

- Maintain a per-section dict of keywords and tickers, e.g. `rates_and_dollar: ["yield", "treasury", "10-year", "fed", "auction", "DGS10", "rate"]`, `commodities: ["oil", "crude", "WTI", "OPEC", "gold", "barrel"]`, etc. One list per section, author it once.
- For each RSS article, score it against each section: `score = (matched_terms_in_title * 2 + matched_terms_in_summary) / total_terms_in_section_list`. Title hits weighted double.
- Attach the top 2–3 articles per section **with their numeric match_score** so a weak match (low score) is visible in the output JSON and in the `runs/` dump.
- A section whose best match_score is below a threshold (start at 0.15, tune later per spec §13) gets *no* articles, which pushes the model toward "no clear catalyst."

### 4.4 The tolerant number validator (Phase 6, build FIRST — load-bearing)

This is what makes invented numbers fail to ship. Build and unit-test it before the model integration. Algorithm:

1. Extract every numeric token from the model's `prose` (regex for numbers, including decimals, percentages, "bps", and dollar amounts).
2. Skip a whitelist entirely: clock times (`8:25`, `HH:MM`), calendar dates, and spelled-out ordinals ("fifth straight session").
3. For each remaining number, round both it and every candidate input number to the same precision and check for a match within a tolerance band: ±`number_tolerance_pct` (default 0.05) for percentages, a small absolute band for prices the model was told to approximate, ±1 for bps.
4. Match against the **full** input set, including the derived figures from 4.2 (weekly sums, spreads, gaps). A number matching nothing after tolerance + whitelist is rejected.
5. On rejection: retry the call once. If it still fails, drop that section to a flat templated line built from numbers + direction alone.

Do NOT use an exact-match check; it would reject normal rounded prose every day and collapse the brief into templates. The tolerance is mandatory (spec §5.6).

### 4.5 The cause check (Phase 6, step 6)

Every causal verb in the prose ("because", "on", "as", "after", "amid", "driven by") must co-occur with a non-null `cause_source_id` pointing to a supplied article. A causal verb with no source tag is stripped or the section is flagged. This proves the cause is *tagged* to a real article; it does not prove the article *supports* it (no entailment check). Low match_score from 4.3 is the warning flag. Trust it only that far (spec §5.6).

### 4.6 The eleven section domain primers (Phase 6, step 4)

One evergreen line each, author-controlled, handed to the model as `primer`. These are the only place structural knowledge enters, so they cannot go stale. Starting set (edit to taste):

- **US Equities:** "The spread between indices signals the move's character: small-cap (Russell) leading means risk-on breadth; mega-cap (Nasdaq) leading alone is narrow."
- **Rates and the Dollar:** "The 10-year is the main equity discount rate; the 2s10s spread is a growth/recession signal; a stronger dollar pressures commodities and exporters."
- **Commodities:** "Oil is a real-time growth and inflation signal that feeds straight into rates and the Fed; gold is a fear and real-rate gauge."
- **Washington and Policy:** "Policy is the standing risk backdrop; energy and Fed content here is usually the cause of the rates and commodities moves above it."
- **Movers:** "Single-name moves are only meaningful above the volume floor; a large move on thin volume is noise."
- **Economic Data Scorecard:** "What matters is the surprise versus expectations, not the absolute number."
- **Earnings on Deck:** "Pre-open and after-close reporters drive intraday volatility in their sector."
- **Watchlist:** "These are the user's tracked names; relevance is personal, not market-wide."
- **Crypto:** "BTC and ETH are a risk-appetite gut check that trades 24/7, so overnight moves preview the equity mood."
- **Volatility and Breadth:** "VIX rises into fear and falls into complacency; a low flat VIX means no hedging demand and little to read into."
- **What to Watch Today:** "Pure schedule, not prediction; it lists known event times only."

---

## Part 5 — Phases 1–7: the Claude Code prompts and gates (Track B)

Each phase is one session. Paste the prompt, approve the plan, verify the gate. The prompts assume `CLAUDE.md` and the three docs are in the repo.

### Phase 1 — Safety net [CC]

> Build roadmap Phase 1. Create the full repo layout from spec §8.1 (sources/, engine/, render/, data/, runs/, .github/workflows/, module stubs). Write requirements.txt and resolve exact pins now for yfinance and anthropic especially (plus pandas, requests, matplotlib, feedparser, jinja2, python-dateutil, pandas-market-calendars, pyyaml). Create the config.yaml skeleton exactly as in spec §8.4, including the resilience, monitoring, narrative, charts, and sections blocks (number_tolerance_pct nested under narrative). Write brief.py with argparse and a --no-send flag, and make --no-send imply NO state write from the very start. Add smoke-test.yml that runs `python brief.py --no-send` on workflow_dispatch.

**Gate:** `smoke-test.yml` runs green on Actions against the stub; a `--no-send` run provably writes no state file. (You trigger the workflow; that part is [HUMAN].)

### Phase 2 — State caching + backfill [CC]

> Build roadmap Phase 2. Implement engine/state.py with load_state() and save_state() using the exact last_run.json schema in the execution guide Part 4.1. Add first-run backfill: when last_run.json is missing, pull 20+ trading days of daily closes per metric, sourcing each metric's history from its morning-primary source (FRED for yields, yfinance for the rest). Implement "yesterday = last trading day" driven off the rolling history, not the calendar. Add the commit-back logic (git config + add + commit + push last_run.json with STATE_COMMIT_PAT) that runs only on a successful Actions run. Wire the workflow checkout to use the PAT.

**Gate:** first run backfills and seeds; second run loads the prior payload; stale detection fires; a successful Actions run commits an updated `last_run.json`. (Setting `STATE_COMMIT_PAT` as a secret is [HUMAN], step 2.4 pattern.)

### Phase 3 — Diff line [CC]

> Build roadmap Phase 3. Implement engine/diff.py: load the previous payload, detect direction flips, levels broken (5d/20d highs/lows from rolling history), and streaks. Select the single reframing event. Graceful degradation: if history is missing or stale, skip the diff line rather than printing wrong deltas. Implement the "quiet tape" output path. Unit-test against seeded fixtures including a post-holiday gap and missing-history.

**Gate:** diff line correct against fixtures including post-holiday gap; degrades to silence, not wrong deltas, on thin history.

### Phase 4 — Top Story engine [CC + HUMAN data entry]

> Build roadmap Phase 4. Implement engine/top_story.py per spec §5: tier-one calendar check first, then z-score standardized large-move check with the raw-trigger floors as eligibility gates (10Y >8bps, WTI >3%, S&P >1%, VIX >15%), tie-break by largest z-score, then the quiet-tape floor. Add the mechanical-move guard that suppresses promotion on listed dates. Consume settled finished-day data only. Implement the floating Top Story slot mechanics. Unit-test each branch.

**[HUMAN] data entry:** hand-author `data/tier_one_calendar.yaml` (FOMC, CPI, NFP, PCE, GDP dates from Fed/BLS/BEA published schedules) and `data/mechanical_moves.yaml` (Russell reconstitution late June, quad witching third Fridays of Mar/Jun/Sep/Dec, S&P add/drop dates, quarter-end rebalances). Claude Code can scaffold the file format and even pre-fill dates it is confident about, but you must verify every date against the official published schedule — these are the most consequential triggers in the system.

**Gate:** every priority branch returns the right Top Story on fixtures; a mechanical date is annotated-not-promoted; a flat day reads "quiet tape."

### Phase 5 — Resilience and data layer [CC]

> Build roadmap Phase 5. Implement sources/prices.py (yfinance pulls for all symbols in spec §7 mapping, carrying rolling history + backfill hook) and sources/fred.py (DGS10, DGS2, DCOILWTICO cross-check, DTWEXBGS). Add the second price source per config second_price_provider (Stooq or Twelve Data) UNLESS Phase 0 proved the runner is never blocked. Health check after pulling (core fields present and numeric). FRED fallback for rates; oil fallback last-resort and date-stamped, preferring "stale" over a multi-day-old print. Stale-field flagging that excludes stale fields from diff, Top Story, and explanation engines. Degraded-banner logic. News and model degradation paths (templated lines). Hard floor (more than hard_floor_missing_threshold missing → send short "data unavailable" notice and exit non-zero). Cron guard in brief.py (fire only inside ~8:25–9:15 CT window AND last_sent_date not today; stamp on success; relabel late sends; print actual send time). Heartbeat per the monitoring config block. Ensure hard floor and fatal errors exit non-zero.

**[HUMAN] after CC:** run the real pipeline on Actions for several mornings with templated why lines (no prose yet) to shake out data/delivery/timing bugs before adding the model.

**Gate:** stale fields render marked and excluded; a forced "too many missing" run sends the notice and exits non-zero; a simulated total stoppage alerts you within a day on the independent channel; the brief runs clean for several mornings.

### Phase 6 — Explanation engine [CC]

> Build roadmap Phase 6. Build in this order: (1) the tolerant number validator from execution guide Part 4.4, with unit tests, FIRST. (2) sources/news.py: parse the RSS feeds in spec §7 with feedparser (verify the exact feed URLs resolve at build time). (3) The matcher from Part 4.3. (4) The per-section context bundle. (5) The single constrained Anthropic API call using the exact system prompt and user-message structure from Part 4.2 and the primers from Part 4.6, model from config. (6) The cause check from Part 4.5. (7) Retry-once then per-section flat templated fallback. (8) Render from validated fields only. (9) Dump each run's structured JSON to runs/. Depth-scaling driven by the confidence field. Never block the brief on the model.

**Gate:** an invented number provably fails to ship (retry then template); an untagged cause is stripped; quiet sections collapse to one honest line; cross-asset synthesis (weekly sums, 2s10s, rotation gaps) passes validation; every run dumps auditable JSON to `runs/`. Audit a few `runs/` dumps by eye.

### Phase 7 — Template and charts [CC]

> Build roadmap Phase 7. Build render/template.html.j2: single-column table layout, fully inline styles, web-safe font stack (Georgia masthead; Consolas/SFMono-Regular monospace for figures — protect tabular numerals). Three fenced zones in reading order (settled recap, the timestamped "This morning so far" snapshot, What to Watch Today). Diff line at the very top, then the At a Glance 3-column table with all ten rows including the one live "This morning" row labeled by pull time. Floating Top Story slot then fixed fallback order. All eleven sections render; one honest line when quiet, the four-ingredient read when there is a real move and real news. Pre-market labeling by actual pull time ("Pre-market as of HH:MM CT" before open, "Early session as of HH:MM CT" after). Degraded banner at top when degraded. Every figure hyperlinks to its source. Color discipline (navy/paper/grey + one gold rule; green/red direction only). Favicons confined to Movers and Watchlist rows (Google s2 service, ticker_domains map, graceful fail). render/charts.py: matplotlib → static PNG → inline CID for the three default-on charts (index %-change bar, yield curve + 10Y trend, WTI 1-month). sources/calendar.py: FMP with Finnhub backup for minor events/earnings only, degrade quietly. Final daily-brief.yml: both cron lines, PAT checkout, all env secrets, workflow_dispatch.

**[HUMAN] before first send:** populate a real `watchlist` in config.yaml (an empty one is the most-skipped block, spec §13).

**Gate:** the brief renders correctly across settled/live/forward zones; figures link to sources; the live zone is fenced and timestamped by actual pull time; charts embed as inline images.

---

## Part 6 — Go-live (Track A)

### 6.1 [HUMAN] Confirm all secrets are set

Before the first real send, the repo needs every secret from spec §8.4: `ANTHROPIC_API_KEY`, `FRED_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY` (if used), `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`, `STATE_COMMIT_PAT`, and the Telegram secrets if the heartbeat uses them.

### 6.2 [HUMAN] First real production send

Trigger `daily-brief.yml` via workflow_dispatch. If it junks, repeat the safe-senders step (it is the same fix). Then audit the brief against the source pages — this is your first real worked example, and per spec Appendix A it is the first time real numbers should be trusted on the page.

### 6.3 [HUMAN] Let the schedule take over

Once a manual run is clean, the two cron lines handle the daily send. Confirm the heartbeat fires if you simulate a miss (e.g. temporarily break the schedule) so you know the dead-man's switch works.

> **DONE when:** a real brief lands in your inbox on the daily schedule, every number audits against its source page, the live zone is fenced and timestamped, and a simulated stoppage reaches you within a day on the independent channel.

---

## Part 7 — The human-only checklist (everything Claude Code cannot do)

Pull this out as your personal punch list. If you are ever stuck waiting on Claude Code for one of these, stop — it is your job:

- [ ] Install Python, git, Node (if npm), Claude Code; authenticate Claude Code.
- [ ] Create GitHub repo (decide public vs private).
- [ ] Create Brevo account; verify single sender; collect SMTP creds.
- [ ] Get FRED, FMP, (Finnhub), Anthropic API keys.
- [ ] Create the fine-grained PAT (`STATE_COMMIT_PAT`).
- [ ] (Optional) Create Telegram bot + chat ID.
- [ ] Set ALL of the above as GitHub Secrets (Claude Code has no access to repo settings).
- [ ] Run the Phase 0 test send on Actions; watch three mornings; do safe-senders.
- [ ] Record the runner-IP finding; decide the second price source.
- [ ] Hand-author and verify `tier_one_calendar.yaml` and `mechanical_moves.yaml` against official schedules.
- [ ] Run Phase 5 several mornings with templated lines before adding the model.
- [ ] Populate a real watchlist before first send.
- [ ] Trigger the first real send; audit against sources; confirm heartbeat works.
- [ ] Quarterly: bump yfinance + anthropic pins, confirm every secret authenticates, re-check the model string, prune `runs/`.

---

## Appendix — Why one phase per session

Claude Code keeps the whole session in its working context. A single session that tries to build all seven phases drifts: it forgets a decision made early, re-derives something inconsistently, or loses track of which "Done when" bars are met. One phase per session, with a commit at each gate, means every session starts clean with `CLAUDE.md` and the three docs as fixed context, and you always have a working fallback to return to. This is slower in wall-clock per phase but far faster to a correct finish, and it matches the spec's own discipline: prove the boring parts first, build state before intelligence, write prose late, style last.
