"""Tests for Task 13: pipeline._assemble wired to BriefView composition."""
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.core.pipeline import run_pipeline


def test_pipeline_produces_brief_view_with_all_sections():
    ctx = BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config())
    out = run_pipeline(ctx, narration_client=None)
    assert out.brief_view is not None
    ids = {s.id for s in out.brief_view.sections}
    expected = {"us_equities", "rates_and_dollar", "commodities", "washington", "movers",
                "economic_data_scorecard", "earnings_on_deck", "watchlist", "crypto",
                "volatility_breadth", "what_to_watch_today"}
    assert expected.issubset(ids)
