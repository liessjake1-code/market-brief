"""Load / save last_run.json — the state cache (spec §5.5, §8.3; roadmap §2).

GitHub Actions is stateless between runs, so the diff line, streaks, z-scores,
and range claims all depend on this small committed JSON. The schema is fixed by
execution-guide Part 4.1.

What lives here (Phase 2):
  - load_state(): read + parse, detect missing / stale (Part 4.1 schema).
  - save_state(): write compact, human-readable JSON.
  - first-run backfill scaffolding: build a fresh state by pulling 20+ trading
    days of daily closes per metric. The actual network pull is injected as a
    callback (the price/FRED layer is Phase 5), so this module stays unit-
    testable without a network.
  - "yesterday = last trading day": derived from rolling history, never the
    calendar, so a post-holiday gap is never printed as a one-day move (spec §5.5).
  - commit_state_back(): on a successful Actions run only, commit last_run.json
    with STATE_COMMIT_PAT (spec §8.3). Never runs locally.

What is NOT here: the real yfinance/FRED pulls (Phase 5), and the daily state
WRITE on a full run (wired into brief.py once the pipeline produces a payload).
The --no-send no-state invariant (Phase 1) gates all of that upstream.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from engine.metrics import METRIC_KEYS, is_yield

SCHEMA_VERSION = 1
STATE_FILENAME = "last_run.json"
RUNS_DIRNAME = "runs"       # per-run structured JSON dumps, committed for auditing (§6.11)
HISTORY_KEEP = 25            # ~25 closes: enough for 20-day high/low + streaks (Part 4.1)
STOCK_HISTORY_KEEP = 10      # per-watchlist/movers stock: session + ~1-week sparkline,
                             # smaller than HISTORY_KEEP to keep the committed file lean
                             # (the week/month windows fill in over ~21 sessions, em dash
                             # until then, same self-heal as the macro metrics).
BACKFILL_MIN_DAYS = 20       # pull at least 20 trading days on first run (spec §5.5)
STALE_TRADING_DAYS = 3       # older than this many trading days => stale (spec §5.5)

# A fetcher returns {metric_key: [close, close, ...]} most-recent-last, sourced
# from each metric's morning-primary source. Injected so Phase 2 has no network.
HistoryFetcher = Callable[[int], dict[str, list[float]]]


@dataclass
class State:
    """Parsed last_run.json plus provenance flags the pipeline needs."""

    data: dict
    path: str
    missing: bool = False     # no file existed; a backfill is expected
    stale: bool = False       # file older than STALE_TRADING_DAYS trading days

    @property
    def metrics(self) -> dict:
        return self.data.get("metrics", {})

    @property
    def stocks(self) -> dict:
        """Per-ticker watchlist/movers data, kept apart from macro `metrics`.

        Backward compatible: a state file written before this feature has no
        `stocks` key, so this returns {} and every accessor below degrades to
        empty rather than raising.
        """
        return self.data.get("stocks", {})

    def history(self, key: str) -> list[float]:
        return list(self.metrics.get(key, {}).get("history", []))

    def stock_history(self, ticker: str) -> list[float]:
        return list(self.stocks.get(ticker, {}).get("history", []))

    def stock_history_dates(self, ticker: str) -> list[str]:
        """ISO dates parallel to stock_history(ticker); empty until accrued."""
        return list(self.stocks.get(ticker, {}).get("history_dates", []))

    def stock_volume(self, ticker: str) -> Optional[float]:
        """Most-recent session volume for a stock; None until first stored."""
        return self.stocks.get(ticker, {}).get("volume")

    def history_dates(self, key: str) -> list[str]:
        """ISO dates parallel to history(key); empty if not yet recorded.

        Backward compatible: state files written before the dates schema simply
        have no history_dates, so this returns [] and charts fall back to an
        undated axis until dates accrue (or a one-time seed backfills them).
        """
        return list(self.metrics.get(key, {}).get("history_dates", []))


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
def state_path(repo_root: Optional[str] = None) -> str:
    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, STATE_FILENAME)


def load_state(
    repo_root: Optional[str] = None,
    *,
    today: Optional[date] = None,
) -> State:
    """Read last_run.json. Flags missing (backfill needed) or stale state.

    Staleness is measured in trading days off last_sent_date, not calendar days,
    so a normal weekend does not trip it (spec §5.5).
    """
    path = state_path(repo_root)
    if not os.path.exists(path):
        return State(data=_empty_state(), path=path, missing=True)

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    _validate_loaded(data)
    today = today or date.today()
    stale = _is_stale(data.get("last_sent_date"), today)
    return State(data=data, path=path, missing=False, stale=stale)


def _empty_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_sent_date": None,
        "sent_today": False,
        "run_timestamp_ct": None,
        "chosen_top_story": None,
        "metrics": {k: _empty_metric(k) for k in METRIC_KEYS},
        # Per-ticker watchlist/movers data, populated on the first real send and
        # seeded per ticker by seed_stock_state() during commit-back.
        "stocks": {},
    }


def _empty_metric(key: str) -> dict:
    m = {"close": None, "prev_close": None, "history": [], "history_dates": []}
    m["change_bps" if is_yield(key) else "change_pct"] = None
    return m


def _empty_stock() -> dict:
    """Scaffold for one watchlist/movers ticker.

    Stocks always carry change_pct (never change_bps): they are equities, not
    rate-like series. `volume` gates the movers floor (config movers_min_volume).
    """
    return {
        "close": None,
        "prev_close": None,
        "history": [],
        "history_dates": [],
        "volume": None,
        "change_pct": None,
    }


def seed_stock_state(data: dict, ticker: str) -> None:
    """Fold a not-yet-tracked ticker into an existing state dict, in place.

    Mirrors the macro-metric seeding done at commit-back: a newly added
    watchlist/movers symbol starts accruing history on its first real send
    without a manual state edit. An already-present ticker is left untouched so
    a seed never clobbers real stored history.
    """
    stocks = data.setdefault("stocks", {})
    if ticker not in stocks:
        stocks[ticker] = _empty_stock()


def _validate_loaded(data: dict) -> None:
    """Fail fast on a malformed state file (spec: diagnose by eye, never guess)."""
    if not isinstance(data, dict):
        raise ValueError("last_run.json is not a JSON object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"last_run.json schema_version {data.get('schema_version')!r} "
            f"!= expected {SCHEMA_VERSION}"
        )
    if "metrics" not in data or not isinstance(data["metrics"], dict):
        raise ValueError("last_run.json missing a 'metrics' object")


def _is_stale(last_sent_date: Optional[str], today: date) -> bool:
    if not last_sent_date:
        return True
    try:
        last = datetime.strptime(last_sent_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return True
    return trading_days_between(last, today) > STALE_TRADING_DAYS


# --------------------------------------------------------------------------- #
# "Yesterday" = last trading day, off rolling history not the calendar
# --------------------------------------------------------------------------- #
def trading_days_between(start: date, end: date) -> int:
    """Count weekday sessions strictly between start and end (exclusive of start).

    Weekend-aware only; exchange holidays are handled at the data layer
    (pandas-market-calendars, Phase 5/7). This is the cheap guard that keeps a
    normal Fri->Mon gap from reading as stale; a holiday Mon is absorbed because
    the comparison that matters ("yesterday") is driven off history length, not
    this count (spec §5.5).
    """
    if end <= start:
        return 0
    days = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:  # Mon-Fri
            days += 1
    return days


def yesterday_close(state: State, key: str) -> Optional[float]:
    """The last settled close for a metric = the most recent history entry.

    Driven off rolling history, never the calendar date, so the comparison after
    a holiday or long weekend references the last session that actually closed
    (spec §5.5). Returns None when history is too thin to compare.
    """
    hist = state.history(key)
    return hist[-1] if hist else None


# --------------------------------------------------------------------------- #
# First-run backfill
# --------------------------------------------------------------------------- #
def backfill(
    fetch_history: HistoryFetcher,
    *,
    days: int = BACKFILL_MIN_DAYS,
) -> State:
    """Seed a fresh State from 20+ trading days of closes per metric.

    The fetcher pulls each metric's history from its morning-primary source
    (FRED for yields, yfinance for the rest); this function only shapes the
    result into the Part 4.1 schema and trims history to HISTORY_KEEP. Called
    when load_state() reports missing (spec §5.5).
    """
    pulled = fetch_history(max(days, BACKFILL_MIN_DAYS))
    data = _empty_state()
    for key in METRIC_KEYS:
        closes = list(pulled.get(key, []))[-HISTORY_KEEP:]
        metric = _empty_metric(key)
        metric["history"] = closes
        # One-time date seed for the backfilled closes via the trading calendar.
        # These are approximate (the data carries no real dates), but they let the
        # chart x-axis be dated immediately; they age out as real dated closes
        # replace them. Returns [] if the calendar is unavailable -> undated axis.
        metric["history_dates"] = _seed_session_dates(len(closes), date.today())
        if closes:
            metric["close"] = closes[-1]
            metric["prev_close"] = closes[-2] if len(closes) >= 2 else None
        data["metrics"][key] = metric
    return State(data=data, path=state_path(), missing=False, stale=False)


def _seed_session_dates(n: int, last_session: date) -> list[str]:
    """ISO dates for `n` NYSE sessions ending at `last_session` (one-time seed).

    A labeling aid for backfilled closes that carry no real date. Never changes a
    value. Degrades to [] when the calendar is unavailable, so charts fall back to
    an undated axis rather than guessing. Real dates are stamped on each later run.
    """
    if n <= 0:
        return []
    try:
        import pandas_market_calendars as mcal

        nyse = mcal.get_calendar("XNYS")
        start = last_session - timedelta(days=n * 2 + 20)
        sched = nyse.schedule(start_date=start, end_date=last_session)
        days = [ts.date().isoformat() for ts in sched.index]
    except Exception:
        return []
    return days[-n:] if len(days) >= n else []


# --------------------------------------------------------------------------- #
# Save
# --------------------------------------------------------------------------- #
def save_state(state: State, *, repo_root: Optional[str] = None) -> str:
    """Write compact, human-readable JSON. Trims each history to HISTORY_KEEP.

    The --no-send no-state invariant (Phase 1) is enforced in brief.py upstream;
    this function unconditionally writes when called, so callers must only call
    it on a real (sending) run.
    """
    path = state_path(repo_root)
    data = state.data
    data.setdefault("schema_version", SCHEMA_VERSION)
    for key in METRIC_KEYS:
        metric = data.get("metrics", {}).get(key)
        if metric and isinstance(metric.get("history"), list):
            metric["history"] = metric["history"][-HISTORY_KEEP:]
            # Trim dates in lockstep so history[i] and history_dates[i] stay aligned.
            if isinstance(metric.get("history_dates"), list):
                metric["history_dates"] = metric["history_dates"][-HISTORY_KEEP:]
    # Trim per-stock history to the smaller STOCK_HISTORY_KEEP (committed-file
    # size), dates in lockstep with closes.
    for stock in data.get("stocks", {}).values():
        if isinstance(stock, dict) and isinstance(stock.get("history"), list):
            stock["history"] = stock["history"][-STOCK_HISTORY_KEEP:]
            if isinstance(stock.get("history_dates"), list):
                stock["history_dates"] = stock["history_dates"][-STOCK_HISTORY_KEEP:]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


# --------------------------------------------------------------------------- #
# Commit-back (Actions only, PAT-authored — spec §8.3)
# --------------------------------------------------------------------------- #
def commit_state_back(*, repo_root: Optional[str] = None) -> bool:
    """Commit + push last_run.json so it counts as repo activity (spec §8.3).

    Runs ONLY on GitHub Actions and ONLY when STATE_COMMIT_PAT is present; never
    locally (CLAUDE.md). Authoring with the PAT is what keeps the scheduled
    workflow from being auto-disabled at 60 days. Returns True if it pushed.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("  state-commit: skipped (not on GitHub Actions)")
        return False
    if not os.environ.get("STATE_COMMIT_PAT"):
        print("  state-commit: skipped (STATE_COMMIT_PAT not set)")
        return False

    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = state_path(root)
    runs_dir = os.path.join(root, RUNS_DIRNAME)
    if not os.path.exists(path) and not os.path.isdir(runs_dir):
        print("  state-commit: skipped (no last_run.json or runs/ to commit)")
        return False

    def run(*cmd: str) -> None:
        subprocess.run(cmd, cwd=root, check=True)

    run("git", "config", "user.name", "market-brief-bot")
    run("git", "config", "user.email", "market-brief-bot@users.noreply.github.com")
    # Stage the state cache and any new per-run audit dumps under runs/. The
    # runs/ JSON (spec §6.11) is what lets the model's output be audited after
    # the fact, so it is committed alongside the state cache. Only stage paths
    # that exist on disk; `git add` errors (exit 128) on a missing pathspec.
    to_stage = [p for p in (STATE_FILENAME, RUNS_DIRNAME) if os.path.exists(os.path.join(root, p))]
    if to_stage:
        run("git", "add", *to_stage)
    # Commit only if staging actually produced changes (a run can add a new
    # runs/ dump even when last_run.json is byte-identical, e.g. the very first
    # run before a state baseline exists).
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=root
    )
    if staged.returncode == 0:
        print("  state-commit: no change to commit (state + runs/ unchanged)")
        return False
    run("git", "commit", "-m", "chore: update state cache + runs/ audit dump [skip ci]")
    run("git", "push")
    print("  state-commit: pushed state cache + runs/ audit dump")
    return True
