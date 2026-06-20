import json
from pathlib import Path
from marketbrief.core.state import load_state, commit_state
from marketbrief.core.enums import RunMode


def test_no_send_writes_no_state(tmp_path: Path):
    p = tmp_path / "last_run.json"
    wrote = commit_state(p, {"x": 1}, mode=RunMode.NO_SEND)
    assert wrote is False
    assert not p.exists()


def test_send_writes_state(tmp_path: Path):
    p = tmp_path / "last_run.json"
    wrote = commit_state(p, {"x": 1}, mode=RunMode.SEND)
    assert wrote is True
    assert json.loads(p.read_text()) == {"x": 1}


def test_no_send_does_not_overwrite_existing_state(tmp_path: Path):
    p = tmp_path / "last_run.json"
    p.write_text(json.dumps({"day": "yesterday"}))
    commit_state(p, {"day": "today"}, mode=RunMode.NO_SEND)
    assert json.loads(p.read_text()) == {"day": "yesterday"}


def test_load_missing_state_returns_empty(tmp_path: Path):
    assert load_state(tmp_path / "nope.json") == {}
