"""state commit-back gate (spec §8.3 / CLAUDE.md invariant).

The git push must run ONLY on GitHub Actions AND with STATE_COMMIT_PAT set AND
when the state file exists. Every gated-off path must be a pure no-op (no git
subprocess at all), so a local run can never push state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from marketbrief.deploy import state_commit as SC


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("STATE_COMMIT_PAT", raising=False)


def _ban_subprocess(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("git subprocess must NOT run on a gated-off path")
    monkeypatch.setattr(SC.subprocess, "run", _boom)


def test_noop_when_not_on_actions(monkeypatch, tmp_path):
    _ban_subprocess(monkeypatch)
    (tmp_path / "last_run.json").write_text("{}")
    assert SC.commit_state_back(repo_root=tmp_path) is False


def test_noop_when_no_pat(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    _ban_subprocess(monkeypatch)
    (tmp_path / "last_run.json").write_text("{}")
    assert SC.commit_state_back(repo_root=tmp_path) is False


def test_noop_when_state_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("STATE_COMMIT_PAT", "pat")
    _ban_subprocess(monkeypatch)
    assert SC.commit_state_back(repo_root=tmp_path) is False


def test_commits_and_pushes_when_fully_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("STATE_COMMIT_PAT", "pat")
    (tmp_path / "last_run.json").write_text("{}")

    calls: list[list[str]] = []

    class _Result:
        returncode = 1  # "git diff --cached --quiet" -> changes staged

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _Result()

    monkeypatch.setattr(SC.subprocess, "run", _fake_run)
    assert SC.commit_state_back(repo_root=tmp_path) is True
    joined = [" ".join(c) for c in calls]
    assert any(c.startswith("git add last_run.json") for c in joined)
    assert any(c.startswith("git commit") for c in joined)
    assert any(c == "git push" for c in joined)


def test_no_commit_when_state_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("STATE_COMMIT_PAT", "pat")
    (tmp_path / "last_run.json").write_text("{}")

    calls: list[list[str]] = []

    class _Result:
        returncode = 0  # diff --cached --quiet -> nothing staged

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _Result()

    monkeypatch.setattr(SC.subprocess, "run", _fake_run)
    assert SC.commit_state_back(repo_root=tmp_path) is False
    joined = [" ".join(c) for c in calls]
    assert not any(c == "git push" for c in joined)
