"""Commit + push last_run.json so it counts as repo activity (spec §8.3).

Runs ONLY on GitHub Actions and ONLY when STATE_COMMIT_PAT is present; never
locally (CLAUDE.md). Authoring with the PAT is what keeps the scheduled workflow
from being auto-disabled at 60 days.

Ported from v1 engine/state.py commit_state_back, trimmed to v2: v2 has no runs/
audit dump, so only last_run.json is staged. The runner step + gates are otherwise
identical (Actions-only, PAT-only, commit-only-if-changed, [skip ci]).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

STATE_FILENAME = "last_run.json"
_BOT_NAME = "market-brief-bot"
_BOT_EMAIL = "market-brief-bot@users.noreply.github.com"


def commit_state_back(*, repo_root: str | Path | None = None,
                      state_filename: str = STATE_FILENAME) -> bool:
    """Commit + push the state cache. Returns True only if it actually pushed.

    Hard no-op (returns False, prints why) when not on GitHub Actions, when the
    PAT is absent, when the state file does not exist, or when there is nothing
    to commit (state byte-identical to HEAD).
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("  state-commit: skipped (not on GitHub Actions)")
        return False
    if not os.environ.get("STATE_COMMIT_PAT"):
        print("  state-commit: skipped (STATE_COMMIT_PAT not set)")
        return False

    root = Path(repo_root) if repo_root else Path.cwd()
    state_path = root / state_filename
    if not state_path.exists():
        print("  state-commit: skipped (no last_run.json to commit)")
        return False

    def run(*cmd: str) -> None:
        subprocess.run(cmd, cwd=str(root), check=True)

    run("git", "config", "user.name", _BOT_NAME)
    run("git", "config", "user.email", _BOT_EMAIL)
    run("git", "add", state_filename)

    # Commit only if staging produced a real change (a re-run with byte-identical
    # state should not create an empty commit).
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(root)
    )
    if staged.returncode == 0:
        print("  state-commit: no change to commit (state unchanged)")
        return False

    run("git", "commit", "-m", "chore: update state cache [skip ci]")
    run("git", "push")
    print("  state-commit: pushed state cache")
    return True
