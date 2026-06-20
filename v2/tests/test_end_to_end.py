from datetime import date
from pathlib import Path
from marketbrief.core.enums import RunMode
import brief


def _cfg(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text("resilience:\n  degraded_stale_threshold: 2\n  hard_floor_missing_threshold: 4\nwatchlist: []\n")
    return p


def test_no_send_builds_brief_and_writes_no_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.NO_SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert "At a Glance" in html
    assert not state.exists()  # the load-bearing invariant, end to end


def test_send_writes_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert state.exists()


def test_real_sources_offline_build_writes_no_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.NO_SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert "At a Glance" in html
    assert not state.exists()


def test_hard_floor_returns_exit_2_and_writes_no_state(tmp_path: Path, monkeypatch):
    # With zero sources, all core fields are missing => hard floor trips.
    from marketbrief.core.pipeline import _fetch, _assess

    monkeypatch.setattr(brief, "run_pipeline", lambda ctx: _assess(_fetch(ctx, [])))

    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == brief.EXIT_HARD_FLOOR
    assert "unavailable" in html.lower()
    assert not state.exists()  # hard floor never writes state
