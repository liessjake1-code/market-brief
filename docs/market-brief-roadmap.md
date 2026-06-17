# Daily Market Brief: Detailed Build Roadmap

Each phase below maps to one item in the spec's Section 11 build order (Phase 0 through Phase 7), decomposed into concrete sub-steps. Build phases top to bottom; within a phase, sub-steps are mostly ordered but parallelizable where noted. Each phase ends with a "Done when" bar you can check against.

A note on wall-clock: Phases 0 and the end-of-5 / end-of-6 audits each gate on a few mornings of real runs. Plan calendar time, not just coding time. You can build the next phase's code while a prior phase's mornings accrue.

---

## Phase 0 — Prove the boring external pieces (the test send)

Goal: answer the three unknowns everything sits on (does free-relay mail reach your inbox, does yfinance give correct numbers at send time, does the Actions schedule fire near 8:30) plus a fourth the spec implies: does Yahoo block the cloud-runner IP.

0.1 Pick the transactional provider. **Brevo is the free default (300/day, permanent).** SendGrid is no longer free (permanent free tier retired May 27, 2025); Resend, Mailtrap, or Amazon SES are the documented free fallbacks. Verify the current free-tier limits at signup.
0.2 Create the account and complete **single-sender verification** (no domain needed). Record the verified `From` address.
0.3 Grab the SMTP relay credentials: host (`smtp-relay.brevo.com` for Brevo), port 587, the username your provider expects (Brevo uses your account/SMTP login; confirm per provider), and the API key as password.
0.4 Create the GitHub repo. Decide **public** (unlimited Actions minutes — recommended) vs private now; add `.gitignore`.
0.5 Write throwaway `test_send.py`: pull ~5 yfinance numbers (the four indices + 10Y), build a plain HTML table, send via `smtplib` STARTTLS on 587 to your Outlook address.
0.6 Set the minimum GitHub Secrets for the test: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`.
0.7 Add a throwaway workflow with `workflow_dispatch` plus a temp schedule near 8:30 CT. **Run it on Actions, not locally** — this is the only way to test runner-IP behavior and scheduler timing.
0.8 First land: when it hits Junk, mark **not junk** and add the sender to the Outlook **safe-senders** list (Settings → Junk email → Safe senders).
0.9 Run ~3 mornings and confirm each of: (a) mail lands in inbox after safe-senders, (b) yfinance numbers are correct vs a live source at send time, (c) the scheduler fires inside ~8:25–9:15, (d) **Yahoo does not block the runner IP** (no NaN/empty pulls from the cloud).
0.10 Record the Yahoo-runner-IP finding — it decides whether a second source is mandatory in Phase 5.3. If you expect to rely on Stooq, also confirm during these mornings that Stooq itself serves the runner (no quota/CAPTCHA block), since it is a best-effort backup, not a guaranteed one.
0.11 Delete `test_send.py` and the throwaway workflow.

**Done when:** a real email from the relay reliably reaches your Outlook inbox on a schedule, with correct numbers, from the cloud runner. You know whether the runner gets blocked.

---

## Phase 1 — Safety net (pins + smoke test + no-state-on-no-send)

Goal: protect every later step before writing anything smart.

1.1 Create the real repo layout from Section 8.1: `sources/`, `engine/`, `render/`, `data/`, `runs/`, `.github/workflows/`, plus the module stubs.
1.2 Write `requirements.txt` and **resolve exact pins at build time** (yfinance and anthropic especially — both are load-bearing pins; plus pandas, requests, matplotlib, feedparser, jinja2, python-dateutil, pandas-market-calendars, pyyaml).
1.3 Create `config.yaml` skeleton: send window, timezone, narrative block (with `number_tolerance_pct` nested under `narrative`, not top-level), chart toggles, `resilience` block (`second_price_source`, `second_price_provider`), `monitoring` block (`heartbeat_enabled`, `heartbeat_cutoff`, `heartbeat_channel`), `sections.breadth: false`, `movers_universe`, `movers_min_volume`, empty `watchlist`, `ticker_domains`.
1.4 Write `brief.py` entry stub with argparse and a `--no-send` flag.
1.5 Implement `--no-send` to **also imply no state write** from the very start (never writes `last_run.json`, never touches `last_sent_date`) so test builds can't poison the next day's diff or idempotency guard.
1.6 Add `smoke-test.yml`: runs `python brief.py --no-send` on `workflow_dispatch`.
1.7 Confirm the smoke test runs green on Actions against the stub.

**Done when:** `smoke-test.yml` builds without sending, dependencies are pinned, and a test build provably leaves state untouched.

---

## Phase 2 — State caching + first-run backfill

Goal: give everything downstream a memory of recent history. Nothing can reference "yesterday" until this exists.

2.1 Define the `last_run.json` schema: key levels, changes, chosen Top Story, `sent_today` flag + date, `last_sent_date`, and a compact rolling history per metric (recent daily closes sufficient for 5-day/20-day high-low and streak counts). Keep it small and human-readable.
2.2 `state.py`: `load_state()` — read the file; detect missing or stale (older than a few trading days).
2.3 `state.py`: `save_state()` — write the compact JSON.
2.4 First-run backfill: when `last_run.json` is missing, pull 20-plus trading days of daily closes per metric from yfinance and seed the rolling history.
2.5 Build the rolling-history structure to serve 5-day/20-day high-low and streak counts directly.
2.6 Implement **"yesterday = last trading day"** driven off the rolling history, not the calendar (Tuesday after a Monday holiday compares to Friday; a 3-day gap is never printed as a 1-day move).
2.7 Commit-back logic: at the end of a successful run, `git config` + add + commit + push `last_run.json` using `STATE_COMMIT_PAT`.
2.8 Wire the workflow `checkout` to use the PAT (sets up the 60-day auto-disable defense, finished in Phase 5/7).
2.9 Test: first run backfills and seeds; second run loads the prior payload; stale detection fires correctly.

**Done when:** a run loads prior state, a missing file backfills cleanly, and a successful run commits an updated `last_run.json` back to the repo via the PAT.

---

## Phase 3 — Diff line ("what changed since yesterday")

Goal: the highest-signal element, computed for free from the cached payload. Depends on Phase 2.

3.1 `diff.py`: load the previous payload.
3.2 Detect direction flips (sign changes vs the last session).
3.3 Detect levels broken (new 5-day/20-day highs/lows from rolling history).
3.4 Detect streaks ("5th straight session").
3.5 Select the single reframing event for the line.
3.6 Graceful degradation: if history is missing or stale, skip the diff line rather than printing wrong deltas; treat range claims as unverified rather than guessing.
3.7 Implement the "quiet tape" output path (used by the Phase 4 quiet-tape floor).
3.8 Unit-test against seeded fixtures (flip, break, streak, gap-after-holiday, missing-history).

**Done when:** the diff line is correct against fixtures including a post-holiday gap, and degrades to silence (not wrong deltas) when history is thin.

---

## Phase 4 — Top Story rules engine (deterministic, no model)

Goal: decide what leads, on settled data only. Depends on Phases 2–3 and the two static YAML files.

4.1 Hand-author `data/tier_one_calendar.yaml`: FOMC, CPI, jobs (NFP), PCE, GDP dates for the year, from Fed/BLS/BEA published schedules. (Data entry — not code.)
4.2 Hand-author `data/mechanical_moves.yaml`: Russell reconstitution (late June), quad witching (third Friday of Mar/Jun/Sep/Dec), S&P add/drop effective dates, month/quarter-end rebalances.
4.3 `top_story.py` step 1: tier-one event today? → promote Washington (FOMC/policy) or Economic Data Scorecard (data releases).
4.4 z-score standardization: rolling 20-day std of daily moves per metric (Section 5.1).
4.5 Raw-trigger floors as eligibility gates: 10Y > 8 bps, WTI > 3%, S&P > 1%, VIX > 15%.
4.6 Tie-break among qualifiers by **largest z-score**, not largest raw move.
4.7 Quiet-tape floor: no tier-one event and nothing clears its trigger → fallback order, diff + Bottom Line read "quiet tape." Do not manufacture a Washington headline.
4.8 Mechanical-move guard: before promoting in step 2, check `mechanical_moves.yaml`; on a listed date, annotate the move as mechanical and **suppress promotion**.
4.9 Enforce that the engine consumes settled finished-day data only (never a pre-market tick).
4.10 Floating Top Story slot mechanics: pull the promoted section out of its fallback position; keep the rest in the fixed order (Section 4.2).
4.11 Test each branch: tier-one day, single large move, multiple qualifiers (z-score tie-break), mechanical date, quiet tape.

**Done when:** every priority branch returns the right Top Story on fixtures, a mechanical date is annotated-not-promoted, and a flat day reads "quiet tape."

---

## Phase 5 — Resilience and the data layer (yfinance is the single point of failure)

Goal: a brief that never silently ships blanks, never silently stops, and degrades honestly. At the end of this phase you have a shippable brief with templated why lines.

5.1 `prices.py`: yfinance pulls for all symbols (indices + futures, `^VIX`, `GC=F`, `BTC-USD`/`ETH-USD`, `DX-Y.NYB`, `^TNX`), carrying rolling history and the first-run backfill hook.
5.2 `fred.py`: FRED pulls with API key — `DGS10`, `DGS2`, `DCOILWTICO` (cross-check only), `DTWEXBGS` (alt dollar).
5.3 **Second price source** for indices/futures/VIX — build it unless Phase 0 proved the runner is never blocked. Stooq (free CSV, no key) is the conventional choice but best-effort (low daily quota, CAPTCHA history, uneven futures/VIX coverage); Twelve Data (free Basic 800/day) is a cleaner alternative for crypto/equities but does not cover indices on the free tier. Set `second_price_provider` in config. If you skip a second source entirely, write down plainly that a Yahoo block = no brief that day.
5.4 Health check after pulling: each core field present and numeric (four indices or futures, 10Y, WTI, dollar index).
5.5 FRED fallback for rates when the yfinance yield pull is missing/NaN; clean for the settled recap. A FRED value standing in for a live pre-market figure is flagged prior-session.
5.6 Oil fallback is last-resort: prefer marking oil **stale** over substituting a possibly multi-day-old FRED print; use FRED only as an explicitly date-stamped last resort, never silently.
5.7 Stale-field flagging: small "stale" marker; exclude stale fields from the diff line, Top Story engine, and explanation engine.
5.8 Degraded-banner logic: trips when the model failed OR a count of fields are stale.
5.9 News degradation path: RSS unavailable → explanation engine falls back to flat templated lines.
5.10 Model degradation path: model call fails → ship templated why lines, log degraded. Never block on the model.
5.11 Hard floor: more than N core fields missing → send a short "data unavailable this morning" notice and exit non-zero (visible failed run).
5.12 Cron guard (`brief.py`): fire only if local Central time is inside ~8:25–9:15 and `last_sent_date` is not today; stamp `last_sent_date` on success (idempotent across both cron lines + retries); relabel late sends; print the actual send time in the footer; the two-cron + window approach handles DST.
5.13 Heartbeat / dead-man's switch (driven by the `monitoring` config block): expected-send ledger reads `last_sent_date`; on a trading day where it isn't today by `heartbeat_cutoff` (e.g. 10:00 CT), fire an alert on the `heartbeat_channel` — an **independent channel** (GitHub's built-in notify-on-workflow-failure at minimum; a Telegram bot ideal, with `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` in Secrets). Ensure hard floor + fatal errors exit non-zero.
5.14 Run the real pipeline on Actions for several mornings with templated why lines; shake out data/delivery/timing bugs before adding prose.

**Done when:** stale fields render marked and excluded, a forced "too many missing" run sends the notice and exits non-zero, a total stoppage alerts you within a day on an independent channel, and the brief has run clean for several mornings.

---

## Phase 6 — Explanation engine (the why lines)

Goal: sample-quality causal reads with numbers exactly as trustworthy as a pure-Python build. Depends on Phases 2–5. Build the validator before the model integration.

6.1 `news.py`: parse RSS (CNBC markets, MarketWatch top stories, Fed press releases) with feedparser — headlines + the summary each item carries. Verify exact feed URLs at build time.
6.2 Pipeline step 1 — compute richer inputs: per metric the 5d/20d high-low, streak count, prior close, change; **and the derived figures** the model is allowed to cite — weekly/multi-day sums, the 2s10s spread, index-vs-index rotation gaps. Anything absent from this set is treated as invented and rejected, so compute everything the model may say.
6.3 Build the matcher: per-section keyword + ticker map; score each candidate article by title + summary overlap; attach the top 2–3 **with their match scores** so a bad match is visible in the output.
6.4 Assemble the per-section context bundle: the section's numbers (with rolling context), its 2–3 scored articles, and a one-line evergreen domain primer you control.
6.5 The single constrained API call: structured object, one entry per section; the model **extracts** reporters' explicit causal claims first, **then writes** using only those reasons plus your numbers.
6.6 Define the structured schema per section: `{level, change, context, cause, cause_source_id, confidence, prose}`.
6.7 **Tolerant number check (build first, load-bearing):** round both the model's number and the candidate input to the same precision; accept within a tolerance band (e.g. ±0.05 for a percentage); whitelist clock times, dates, and spelled-out ordinals; match against the **full** input set including derived figures; reject → retry once → flat templated line. An exact-match check would collapse the brief into templates daily — the tolerance is mandatory.
6.8 Cause check: every causal claim must carry a `cause_source_id` pointing to a supplied article; a causal verb with no source tag is flagged/stripped. This proves the cause is tagged to a real article, not that the article supports it; treat it only that far. Low match scores from 6.3 are the cheap mitigation.
6.9 Retry-once then per-section flat templated fallback.
6.10 Render from validated fields only (the template enforces house style, not the model).
6.11 Dump each run's structured JSON to `runs/` for read-by-eye auditing.
6.12 Depth-scaling: `confidence` drives length; low confidence + no source → one honest line; the model is explicitly allowed and encouraged to write "no clear catalyst."
6.13 Model choice from config (`claude-sonnet-4-6`); the failure fallback to templated lines never blocks the brief.
6.14 Audit the `runs/` dumps for a few days; tune the match-score threshold if it reaches for thin causes instead of saying "no clear catalyst."

**Done when:** an invented number provably fails to ship (retry then template), an untagged cause is stripped, quiet sections collapse to one honest line, cross-asset synthesis (weekly sums, 2s10s, rotation gaps) passes validation, and every run dumps auditable JSON.

---

## Phase 7 — Email-safe template and charts

Goal: the editorial look, surviving email-client constraints, rendering only validated fields. Build last.

7.1 `template.html.j2`: single-column table layout, fully inline styles, web-safe font stack (Georgia/serif masthead; `Consolas, "SFMono-Regular", monospace` for figures). Tabular numerals are the signature — protect them.
7.2 Three zones in reading order: settled recap (bulk), the fenced "This morning so far" snapshot (tinted block or labeled rule, every figure timestamped), and What to Watch Today.
7.3 Top of email: the diff line at the very top, then the At a Glance 3-column table — `Category | Latest | Why, in brief` — with all ten rows including the single live "This morning" row labeled by pull time.
7.4 Render the floating Top Story slot followed by the fixed fallback order; the promoted section is pulled out and removed from its fallback position.
7.5 Section catalog render: all eleven always appear; one honest line when quiet, the four-ingredient read (level in context, grounded driver, cross-link, forward hook) when there's a real move and real news.
7.6 Pre-market labeling by **actual pull time**: "Pre-market as of HH:MM CT" before the open, "Early session as of HH:MM CT" after, preferring the cash index over the future after the open. The thin-volume floor applies here too.
7.7 Degraded banner at the top of the brief itself whenever the run is degraded.
7.8 Every figure hyperlinks to its source page (Yahoo quote, FRED series, article URL, provider page).
7.9 Color discipline: ink navy / paper / card white / hairline / one gold rule; green and red carry direction only — resist a second accent.
7.10 Favicons confined to Movers and Watchlist rows (Google s2 favicon service, `ticker_domains` map, graceful fail so the row still reads from text).
7.11 `charts.py`: matplotlib → static PNG → inline (CID) attachments. Wire the three default-on charts last: index daily %-change bar, yield curve + 10Y trend, WTI 1-month. Others stay behind flags.
7.12 `calendar.py`: FMP (Finnhub backup) for minor "What to Watch" events and earnings — used only for secondary content, never the tier-one trigger; degrade quietly when down.
7.13 Final `daily-brief.yml`: both cron lines (CDT + CST), PAT checkout, all env secrets, `workflow_dispatch` for manual runs.
7.14 Populate a **real watchlist** in `config.yaml` before first send — an empty one is the most-skipped block.
7.15 First real production send. If junked, repeat the safe-senders step. Audit the brief against source pages — this is the first real worked example.

**Done when:** the brief renders correctly across the settled/live/forward zones, figures link to sources, the live zone is fenced and timestamped by actual pull time, charts embed as inline images, and a real send lands in the inbox audited against sources.

---

## Ongoing — Longevity pass (Section 13), quarterly

Not a build phase, but the reason the project survives year two. Put a recurring reminder.

- Run `smoke-test.yml` against a fresh yfinance and **bump the yfinance and anthropic pins deliberately** — pin-and-forget is how this dies silently.
- Confirm every secret still authenticates (FMP, Finnhub, Anthropic, FRED, the email provider, and the Telegram bot token if the heartbeat uses it).
- Re-check the current model string; `claude-sonnet-4-6` will eventually retire (the engine fails into templated lines, so the only warning is the degraded banner).
- `runs/` retention: keep ~90 days, archive or delete older. Squash the state-commit history occasionally if it bloats.
- Keep the repo public for unlimited Actions minutes if you can.
- Monthly editorial skim of `runs/`: cut any section that's been one honest line for weeks; spot-check whether the "why" was right on big days; tighten the match-score threshold if it reaches for thin causes.
