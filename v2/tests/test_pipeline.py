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
