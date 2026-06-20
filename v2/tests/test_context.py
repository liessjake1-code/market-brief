from datetime import date
import pytest
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.models import ComputedNumbers


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
