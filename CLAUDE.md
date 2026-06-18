# Project: Daily Market Brief

An automated weekday market brief, emailed at 8:30 AM Central via GitHub Actions.
It reports a finished, settled trading day plus a clearly fenced live pre-market
snapshot, with every number sourced and every "why" traced to real reporting.

## Source of truth (read these before any task)
- `docs/daily_market_brief_SPEC.md` — the full design. This is authoritative.
- `docs/market-brief-roadmap.md` — the phase order and "Done when" bars.
- `docs/claude-code-execution-guide.md` — the runbook, including pre-decided
  artifacts (state schema, model prompt, matcher, validators, primers in Part 4).
  Use these exactly; do not invent your own versions.
- `START_HERE.md` — the human operator's ordered checklist (Track A). Not your
  task list; it tells the human what to do. Read it so you know which steps are
  the human's and where the handoffs are.

The spec's Section 10 is the decision log. Treat it as authoritative; do not
re-litigate settled decisions.

## Files already present (do NOT recreate these)
- `data/tier_one_calendar.yaml` and `data/mechanical_moves.yaml` are already
  built and source-verified (FOMC/CPI/NFP/PCE/GDP and witching/Russell/S&P dates
  for 2026). In Phase 4, USE them as-is; do not overwrite or regenerate them.
  They carry inline source URLs and `# VERIFY` markers the human will confirm.
- `START_HERE.md`, `CLAUDE.md`, `.gitignore`, and the three `docs/` files are
  also already present. Everything else is yours to build in Phases 1-7.

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
writing code. After each phase, ensure the phase's "Done when" bar is met before
moving on. When the execution guide says "use the artifact from Part 4," use that
exact schema/prompt/formula rather than designing your own.

## Context handoff (ALWAYS do this proactively)
When the chat gets long (or after finishing a big chunk of work), do NOT wait to be
asked: tell the human plainly that the chat is getting long, then give them a
ready-to-paste transfer prompt for a NEW chat. Format it as a single fenced code
block the human can copy verbatim. The transfer prompt must include: which branch
we are on and that build/phases mirrors to main, the exact state of the work, what
is done, what remains (with the user's firm decisions), the test command, and any
TEMPORARY flags to restore. Make resuming in a fresh chat zero-friction.
