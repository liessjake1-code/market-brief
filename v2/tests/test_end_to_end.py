from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from marketbrief.core.enums import RunMode
import brief

CT = ZoneInfo("America/Chicago")


def _cfg(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text("resilience:\n  degraded_stale_threshold: 2\n  hard_floor_missing_threshold: 4\nwatchlist: []\n")
    return p


def test_no_send_builds_brief_and_writes_no_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    code, html, ctx = brief.build_brief(
        mode=RunMode.NO_SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert "US Equities" in html
    assert not state.exists()  # the load-bearing invariant, end to end


def test_build_brief_never_writes_state_even_on_send_mode(tmp_path: Path, monkeypatch):
    # build_brief is a pure builder: it must not write state regardless of mode.
    # State is the orchestrator's job (run_send), only after an actual send.
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    code, html, ctx = brief.build_brief(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert not state.exists()


def test_run_send_inside_window_sends_and_writes_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    sent: list[tuple] = []

    def _fake_send(subject, html, *, inline_images=None, text_fallback=None):
        sent.append((subject, html, inline_images))

    code = brief.run_send(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state,
        today=date(2026, 6, 20), smtp_sender=_fake_send,
        now=datetime(2026, 6, 20, 8, 30, tzinfo=CT),
    )
    assert code == 0
    assert len(sent) == 1
    assert sent[0][0].startswith("Morning Market Brief")
    assert state.exists()
    import json
    assert json.loads(state.read_text())["last_sent_date"] == "2026-06-20"


def test_run_send_skipped_by_guard_writes_no_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    sent: list[tuple] = []

    code = brief.run_send(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state,
        today=date(2026, 6, 20), smtp_sender=lambda *a, **k: sent.append(a),
        now=datetime(2026, 6, 20, 6, 0, tzinfo=CT),  # before the window
    )
    assert code == 0
    assert sent == []
    assert not state.exists()  # guard-skipped send writes no state


def test_run_send_no_send_mode_writes_preview_no_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "last_run.json"
    sent: list[tuple] = []

    code = brief.run_send(
        mode=RunMode.NO_SEND, config_path=_cfg(tmp_path), state_path=state,
        today=date(2026, 6, 20), smtp_sender=lambda *a, **k: sent.append(a),
    )
    assert code == 0
    assert sent == []
    assert not state.exists()
    assert (tmp_path / "brief.preview.html").exists()


def test_hard_floor_returns_exit_2_and_writes_no_state(tmp_path: Path, monkeypatch):
    # With zero sources, all core fields are missing => hard floor trips.
    from marketbrief.core.pipeline import _fetch, _assess

    monkeypatch.setattr(brief, "run_pipeline", lambda ctx: _assess(_fetch(ctx, [])))

    state = tmp_path / "last_run.json"
    code, html, ctx = brief.build_brief(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == brief.EXIT_HARD_FLOOR
    assert "unavailable" in html.lower()
    assert ctx is None
    assert not state.exists()  # hard floor never writes state
