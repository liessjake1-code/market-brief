# Build Handoff — resume at Phase 7 (final build phase)

This is a transfer prompt for a fresh Claude Code session. Phases 1–6 are built,
committed, and green (106 tests on Python 3.12). Only Phase 7 remains, plus the
Track A (human) go-live punch list at the bottom.

## How to resume (paste to the new session)

> Read CLAUDE.md, progress.md, HANDOFF_PHASE7.md, and the three docs in docs/ in
> full before doing anything. We are on branch `build/phases`. Phases 1–6 are
> committed and 106 tests pass on Python 3.12 (run them with:
> `uv run --with pytest --with pyyaml --with requests --with pandas --with feedparser --python 3.12 python -m pytest -q`).
> Confirm the two-track split (I do all external/Track A steps; you write code
> only and never claim to have done my steps). Then build roadmap Phase 7 per
> execution guide Part 5 / Phase 7, plan first and wait for my approval. Do not
> re-litigate settled decisions or rebuild earlier phases.

## State of the build (what's done)

- **Branch:** `build/phases` (off `main`). Commits: Phase 1 `28f22bd`, Phase 2
  `082ca1b`, Phase 3 `4ced7f8`, Phase 4 `6bd9e13`, Phase 5 `9dffd9d`, Phase 6
  `b231a42`. Nothing pushed yet — push is a human/explicit step.
- **Test runner:** no local 3.12; use `uv run --with pytest --with pyyaml --with
  requests --with pandas --with feedparser --python 3.12 python -m pytest -q`.
  yfinance/anthropic are imported lazily so tests don't need them.
- **Offline seam:** `MARKET_BRIEF_OFFLINE=1` makes `brief.py` synthesize clean
  placeholder fields and skip all network + the model. The smoke workflow and the
  no-send invariant test use it.

### Modules in place (do not rebuild)
- `engine/`: metrics, state (Part 4.1 schema, backfill, commit-back),
  diff (flips/breaks/streaks/quiet-tape), top_story (tier-one→z-score→quiet,
  mechanical guard), calendars (loads the two YAMLs), schedule (cron window,
  premarket/early-session label), heartbeat, config, validator (load-bearing),
  matcher, primers, narrative (single Anthropic call + validate/retry/template +
  runs/ dump).
- `sources/`: symbols, quality (Field/health/degraded/hard-floor), prices
  (yfinance + FRED fallback + oil-stale rule; **note the `_select_close`
  MultiIndex handling — yfinance 1.4.1 returns `('Close', symbol)` columns**),
  fred, backup_prices (Stooq), news (RSS).
- `render/`: send (smtplib relay), templated (flat why-lines), `template.html.j2`
  is still the **Phase 7 placeholder** — this is the main thing to build.
- `brief.py`: full pipeline (gather→health→hard-floor→narrative→build→send→state),
  no-state-on-no-send invariant preserved via `_commit_state`.
- Workflows: `smoke-test.yml` (done), `daily-brief.yml` (done: two DST crons, PAT
  checkout, all secrets).

## Phase 7 — what to build (roadmap §7, execution guide Part 5 / Phase 7)

1. **`render/template.html.j2`**: single-column table layout, fully inline styles,
   web-safe stack (Georgia masthead; `Consolas, "SFMono-Regular", monospace` for
   figures — tabular numerals are the signature). Three fenced zones: settled
   recap (bulk), the timestamped "This morning so far" snapshot, What to Watch
   Today. Diff line at the very top, then the At a Glance 3-col table (all ten
   rows incl the one live "This morning" row). Floating Top Story slot then the
   fixed fallback order. All eleven sections render: one honest line when quiet,
   the four-ingredient read when there's a real move + news. Degraded banner at
   top. Every figure hyperlinks to its source. Color discipline (navy/paper/grey
   + one gold rule; green/red direction only). Favicons confined to Movers +
   Watchlist (Google s2 service, `ticker_domains` map, graceful fail).
2. **Pre-market labeling by actual pull time** — already implemented in
   `engine/schedule.py` (`premarket_label`); wire it into the live zone.
3. **`render/charts.py`**: matplotlib → static PNG → inline CID. Three default-on
   charts: index %-change bar, yield curve + 10Y trend, WTI 1-month. Others
   behind the existing config flags. Wire CID attachments into `render/send.py`
   (it currently sends HTML only — extend `build_message` for related/inline
   images).
4. **`sources/calendar.py`**: FMP (Finnhub backup) minor events + earnings for
   "What to Watch" / "Earnings on Deck" only — never the tier-one trigger.
   Degrade quietly when down (FMP_API_KEY / FINNHUB_API_KEY).
5. Replace the interim `_render_templated_html` in `brief.py` with Jinja render
   from validated fields only; keep the offline seam and the no-state invariant.
6. Tests: template renders without error from a fixture payload (settled/live/
   forward zones present, degraded banner toggles, favicons confined); charts
   produce non-empty PNG bytes; calendar degrades to [] on failure.

**Gate:** brief renders across settled/live/forward zones; figures link to
sources; live zone fenced + timestamped by actual pull time; charts embed as
inline images. (The real-send half is Track A.)

## A note on what was found during the build
- **yfinance 1.4.1 returns MultiIndex columns** (`('Close', '^GSPC')`). The naive
  `df["Close"]` selector silently returned nothing; caught only via a live pull.
  Fixed in `sources/prices.py::_select_close` with a regression test. If pins are
  bumped (quarterly, spec §13), re-run a live pull and re-check this shape.

---

## Track A punch list (HUMAN-only — Claude Code cannot do these)

Collected across the build. None block writing Phase 7 code; they block the
real send / go-live.

- [ ] **Verify Phase 1–6 on Actions:** trigger `smoke-test.yml` (Actions tab →
      Run workflow). It needs no secrets and runs offline-seam + pytest on the
      3.12 runner. Confirm green. This closes the runner-side gate for everything
      built so far in one shot.
- [ ] **Phase 0 cron-timing unknown (c):** still only manual-proven. Watch ~2–3
      real scheduled mornings once `daily-brief.yml` is live, or accept it during
      Phase 5's "several mornings" step. Record the runner-IP finding (no Yahoo
      block seen so far).
- [ ] **Secrets for the real send** (repo Settings → Secrets and variables →
      Actions), per spec §8.4 — names only: `ANTHROPIC_API_KEY`, `FRED_API_KEY`,
      `FMP_API_KEY`, `FINNHUB_API_KEY` (optional), `SMTP_HOST`, `SMTP_USER`,
      `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`, `STATE_COMMIT_PAT` (fine-grained,
      contents:write, this repo), and Telegram secrets only if the heartbeat uses
      Telegram. (SMTP_* + EMAIL_* are already set from Phase 0.)
- [ ] **STATE_COMMIT_PAT** specifically — needed for the state commit-back and the
      60-day anti-auto-disable. Not yet set.
- [ ] **Re-verify the two YAMLs** (`data/tier_one_calendar.yaml`,
      `data/mechanical_moves.yaml`) against the agency/exchange URLs in their
      headers; they carry `# VERIFY` markers (Feb-11 NFP, Jun-18 witching shift,
      shutdown-disrupted H1 PCE/GDP). Set a quarterly refresh reminder.
- [ ] **Populate a real `watchlist`** in `config.yaml` before first send (empty is
      the most-skipped block, spec §13).
- [ ] **Decide the second price source** (currently provisional `stooq`) based on
      the runner-IP finding (spec Decision 18).
- [ ] **First real production send:** trigger `daily-brief.yml` via
      workflow_dispatch; if junked, repeat the Outlook safe-senders step; audit
      every number against its source page.
- [ ] **Confirm the heartbeat** fires on a simulated miss (dead-man's switch).
