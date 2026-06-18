"""Phase 1 gate as a regression test (spec §8.5; CLAUDE.md; roadmap §1.5).

The load-bearing invariant: `python brief.py --no-send` must write NO state.
It must never create `last_run.json` and never touch `last_sent_date`. A test
build that poisons the next day's diff or the idempotency guard is exactly the
failure this invariant prevents, so it is locked down with a test from day one.
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(REPO_ROOT, "last_run.json")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, MARKET_BRIEF_OFFLINE="1")  # deterministic, no network
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "brief.py"), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_no_send_writes_no_state_file() -> None:
    """A --no-send run leaves last_run.json absent (or untouched if present)."""
    state_existed = os.path.exists(STATE_FILE)
    mtime_before = os.path.getmtime(STATE_FILE) if state_existed else None

    result = _run("--no-send")

    assert result.returncode == 0, result.stderr
    if state_existed:
        # Never mutate an existing state file under --no-send.
        assert os.path.getmtime(STATE_FILE) == mtime_before
    else:
        # And never create one.
        assert not os.path.exists(STATE_FILE), "--no-send must not create last_run.json"


def test_no_send_run_succeeds_and_reports_no_state_write() -> None:
    """The run exits clean and declares the invariant in its output."""
    result = _run("--no-send")
    assert result.returncode == 0, result.stderr
    assert "no write" in result.stdout.lower()
