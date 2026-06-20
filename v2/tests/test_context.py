from datetime import date
import pytest
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.models import ComputedNumbers, Field, Article


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_context_is_immutable():
    ctx = _ctx()
    with pytest.raises(Exception):
        ctx.mode = RunMode.SEND  # frozen


def test_with_updates_returns_new_context():
    ctx = _ctx()
    nums = ComputedNumbers(values={"sp500": 5000.0})
    new = ctx.with_updates(numbers=nums)
    assert new.numbers.values["sp500"] == 5000.0
    assert ctx.numbers.values == {}  # original untouched
    assert new is not ctx


def test_with_updates_sets_resolved_fields_and_articles():
    ctx = _ctx()
    new = ctx.with_updates(
        resolved_fields={"sp500": Field(metric="sp500", value=5000.0, source="yfinance")},
        articles=[Article(source_id="cnbc-1", title="x")],
    )
    assert new.resolved_fields["sp500"].value == 5000.0
    assert new.articles[0].source_id == "cnbc-1"
    assert ctx.resolved_fields == {}  # original untouched
    assert ctx.articles == []
