"""Phase 2 — state caching + backfill (spec §5.5, §8.3; roadmap §2.9 gate).

Gate: first run backfills and seeds; second run loads the prior payload; stale
detection fires; "yesterday" is driven off history not the calendar.
"""

from __future__ import annotations

import json
import os
from datetime import date

import pytest

from engine import state as S
from engine.metrics import METRIC_KEYS, is_yield


# --- fixtures ------------------------------------------------------------- #
def _fake_fetcher(days: int) -> dict[str, list[float]]:
    """Deterministic ascending closes per metric, length `days`."""
    return {k: [100.0 + i for i in range(days)] for k in METRIC_KEYS}


@pytest.fixture
def repo(tmp_path):
    return str(tmp_path)


# --- load: missing -------------------------------------------------------- #
def test_load_missing_flags_backfill(repo):
    st = S.load_state(repo)
    assert st.missing is True
    assert set(st.metrics.keys()) == set(METRIC_KEYS)


# --- backfill seeds schema correctly -------------------------------------- #
def test_backfill_seeds_history_close_and_prev(repo):
    st = S.backfill(_fake_fetcher, days=22)
    for k in METRIC_KEYS:
        m = st.metrics[k]
        assert len(m["history"]) == 22
        assert m["close"] == m["history"][-1]
        assert m["prev_close"] == m["history"][-2]
        # Yields carry change_bps, everything else change_pct (Part 4.1).
        if is_yield(k):
            assert "change_bps" in m and "change_pct" not in m
        else:
            assert "change_pct" in m and "change_bps" not in m


def test_backfill_trims_to_history_keep(repo):
    st = S.backfill(_fake_fetcher, days=200)
    assert all(len(st.metrics[k]["history"]) == S.HISTORY_KEEP for k in METRIC_KEYS)


# --- save -> load round trip ---------------------------------------------- #
def test_save_then_load_round_trips(repo):
    st = S.backfill(_fake_fetcher, days=22)
    st.data["last_sent_date"] = "2026-06-16"
    path = S.save_state(st, repo_root=repo)
    assert os.path.exists(path)

    raw = json.loads(open(path).read())
    assert raw["schema_version"] == S.SCHEMA_VERSION

    loaded = S.load_state(repo, today=date(2026, 6, 17))
    assert loaded.missing is False
    assert loaded.metrics["sp500"]["close"] == 121.0  # 100+21


# --- history_dates: dated x-axis schema (redesign) ------------------------ #
def test_backfill_seeds_history_dates_aligned():
    st = S.backfill(_fake_fetcher, days=22)
    for k in METRIC_KEYS:
        dates = st.metrics[k]["history_dates"]
        # Seeded dates align 1:1 with closes (calendar available in the test env).
        assert len(dates) == len(st.metrics[k]["history"])
        assert all(isinstance(d, str) for d in dates)


def test_history_dates_trimmed_in_lockstep(repo):
    st = S.backfill(_fake_fetcher, days=200)
    S.save_state(st, repo_root=repo)
    loaded = S.load_state(repo)
    for k in METRIC_KEYS:
        assert len(loaded.history_dates(k)) == len(loaded.history(k)) == S.HISTORY_KEEP


def test_old_state_without_dates_still_loads(repo):
    # Backward compatibility: a pre-schema file (no history_dates) loads cleanly
    # and history_dates() returns [] rather than raising.
    st = S.backfill(_fake_fetcher, days=5)
    for k in METRIC_KEYS:
        st.metrics[k].pop("history_dates", None)
    st.data["last_sent_date"] = "2026-06-16"
    S.save_state(st, repo_root=repo)
    loaded = S.load_state(repo, today=date(2026, 6, 17))
    assert loaded.history_dates("sp500") == []
    assert len(loaded.history("sp500")) > 0   # closes load fine without dates


def test_save_is_human_readable_indented(repo):
    st = S.backfill(_fake_fetcher, days=5)
    path = S.save_state(st, repo_root=repo)
    text = open(path).read()
    assert "\n  " in text  # indented, not single-line


# --- stale detection (trading days, not calendar) ------------------------- #
def test_fresh_state_not_stale_over_weekend(repo):
    st = S.backfill(_fake_fetcher, days=5)
    st.data["last_sent_date"] = "2026-06-12"  # Friday
    S.save_state(st, repo_root=repo)
    # Monday: 0 trading days strictly between Fri and Mon -> not stale.
    loaded = S.load_state(repo, today=date(2026, 6, 15))
    assert loaded.stale is False


def test_old_state_is_stale(repo):
    st = S.backfill(_fake_fetcher, days=5)
    st.data["last_sent_date"] = "2026-06-01"
    S.save_state(st, repo_root=repo)
    loaded = S.load_state(repo, today=date(2026, 6, 17))
    assert loaded.stale is True


def test_missing_last_sent_date_is_stale(repo):
    st = S.backfill(_fake_fetcher, days=5)
    st.data["last_sent_date"] = None
    S.save_state(st, repo_root=repo)
    loaded = S.load_state(repo, today=date(2026, 6, 17))
    assert loaded.stale is True


# --- trading-days helper -------------------------------------------------- #
def test_trading_days_between_skips_weekends():
    # Fri 2026-06-12 -> Mon 2026-06-15 == 1 session (Mon), weekend skipped.
    assert S.trading_days_between(date(2026, 6, 12), date(2026, 6, 15)) == 1
    # Same day or backwards == 0.
    assert S.trading_days_between(date(2026, 6, 15), date(2026, 6, 15)) == 0


# --- yesterday = last trading day, off history ---------------------------- #
def test_yesterday_close_is_last_history_entry(repo):
    st = S.backfill(_fake_fetcher, days=10)
    assert S.yesterday_close(st, "sp500") == st.metrics["sp500"]["history"][-1]


def test_yesterday_close_none_when_history_empty(repo):
    st = S.load_state(repo)  # missing -> empty histories
    assert S.yesterday_close(st, "sp500") is None


def test_post_holiday_gap_compares_to_last_session_not_calendar(repo):
    """A 3-day gap must compare to the last real session, not a calendar day.

    History is [.., A, B]; "yesterday" is B (the last close) regardless of how
    many calendar days passed since it. This is the spec §5.5 guarantee.
    """
    st = S.backfill(_fake_fetcher, days=5)
    last = st.metrics["sp500"]["history"][-1]
    # Simulate the run happening after a long weekend: today is far from last_sent.
    st.data["last_sent_date"] = "2026-06-12"
    assert S.yesterday_close(st, "sp500") == last


# --- schema validation fails fast ----------------------------------------- #
def test_bad_schema_version_raises(repo):
    path = S.state_path(repo)
    with open(path, "w") as fh:
        json.dump({"schema_version": 999, "metrics": {}}, fh)
    with pytest.raises(ValueError):
        S.load_state(repo)


def test_missing_metrics_object_raises(repo):
    path = S.state_path(repo)
    with open(path, "w") as fh:
        json.dump({"schema_version": S.SCHEMA_VERSION}, fh)
    with pytest.raises(ValueError):
        S.load_state(repo)


# --- commit-back is a no-op off Actions ----------------------------------- #
def test_commit_back_skipped_off_actions(repo, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert S.commit_state_back(repo_root=repo) is False


# --- commit-back stages a runs/ dump even with no state baseline ----------- #
def _init_git_repo(root: str) -> None:
    import subprocess

    def run(*cmd: str) -> None:
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)

    run("git", "init", "-q")
    # A bare remote so `git push` succeeds without a network.
    remote = os.path.join(root, "_remote.git")
    subprocess.run(["git", "init", "-q", "--bare", remote], check=True, capture_output=True)
    run("git", "remote", "add", "origin", remote)
    run("git", "config", "user.email", "seed@example.com")
    run("git", "config", "user.name", "seed")
    run("git", "commit", "-q", "--allow-empty", "-m", "seed")
    run("git", "branch", "-M", "main")
    run("git", "push", "-q", "-u", "origin", "main")


def test_commit_back_commits_runs_dump_without_state_baseline(repo, monkeypatch):
    """First-run scenario: a new runs/ dump exists but no last_run.json was ever
    committed, so the state file is byte-identical to (absent in) the index. The
    commit-back must still commit the audit dump rather than no-op."""
    import subprocess

    _init_git_repo(repo)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("STATE_COMMIT_PAT", "x")

    runs_dir = os.path.join(repo, S.RUNS_DIRNAME)
    os.makedirs(runs_dir, exist_ok=True)
    with open(os.path.join(runs_dir, "2026-06-18.json"), "w") as fh:
        json.dump({"degraded": True}, fh)

    assert S.commit_state_back(repo_root=repo) is True
    # The dump is now tracked in HEAD.
    tracked = subprocess.run(
        ["git", "ls-files", S.RUNS_DIRNAME], cwd=repo, capture_output=True, text=True
    ).stdout
    assert "2026-06-18.json" in tracked


def test_commit_back_no_op_when_nothing_changed(repo, monkeypatch):
    """Second-run scenario with no new dump and identical state: clean no-op."""
    _init_git_repo(repo)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("STATE_COMMIT_PAT", "x")
    # An empty runs/ dir exists (so the early-return doesn't fire) but nothing to stage.
    os.makedirs(os.path.join(repo, S.RUNS_DIRNAME), exist_ok=True)
    assert S.commit_state_back(repo_root=repo) is False
