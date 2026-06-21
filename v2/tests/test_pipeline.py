from datetime import date
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_pipeline_fetches_and_assembles(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    out = run_pipeline(_ctx())
    assert "yfinance" in out.facts
    assert out.resolved_fields  # resolver produced fields
    assert any(s.id == "us_equities" for s in out.sections)
    assert out.health.hard_floor_tripped is False


def test_movers_board_flows_to_section_via_injected_universe(monkeypatch):
    """A populated universe downloader -> ranked board -> non-quiet Movers section."""
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)
    cfg = Config(movers_universe=["NVDA", "PFE", "AAPL"])
    ctx = BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=cfg)
    moves = {"NVDA": [100.0, 105.0], "PFE": [100.0, 96.0], "AAPL": [100.0, 101.0]}
    out = run_pipeline(ctx, universe_downloader=lambda sym, days: moves.get(sym, []))
    assert out.mover_board is not None and out.mover_board.has_rows
    movers_sec = next(s for s in out.sections if s.id == "movers")
    assert movers_sec.quiet is False
    day = next(p for p in movers_sec.mover_board.periods if p.label == "Day")
    assert day.winners[0].ticker == "NVDA" and day.losers[0].ticker == "PFE"


def test_movers_quiet_when_universe_empty(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    out = run_pipeline(_ctx())  # default Config has empty movers_universe
    movers_sec = next(s for s in out.sections if s.id == "movers")
    assert movers_sec.quiet is True


def test_failing_source_is_isolated():
    class BoomSource:
        name = "boom"
        def fetch(self, ctx): raise RuntimeError("network down")
    out = run_pipeline(_ctx(), sources=[BoomSource()], sections=[])
    assert out.facts["boom"].health == SourceHealth.FAILED
    # brief still produced a context, did not crash
    assert isinstance(out, BriefContext)


def test_failing_section_is_isolated():
    class BoomSection:
        id = "boom"; order = 1
        def build(self, ctx): raise RuntimeError("render error")
        def is_quiet(self, ctx): return False
    out = run_pipeline(_ctx(), sources=[], sections=[BoomSection()])
    # boom section dropped, but pipeline finished
    assert all(s.id != "boom" for s in out.sections)
