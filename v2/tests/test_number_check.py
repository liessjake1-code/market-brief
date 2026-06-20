from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Cause, ComputedNumbers
from marketbrief.narrate.number_check import validate_prose, NumberCheck


def _ctx(values):
    return BriefContext(
        run_date=date(2026, 6, 22), mode=RunMode.FULL, config=Config(),
        numbers=ComputedNumbers(values=values),
    )


def test_rounded_number_consistent_with_input_passes():
    r = validate_prose("oil traded near 76 dollars", [76.12])
    assert r.ok


def test_invented_number_rejected():
    r = validate_prose("the index rose 12 percent", [0.4, 76.12])
    assert not r.ok
    assert "12" in "".join(r.rejected)


def test_whitelist_skips_dates_times_ordinals_and_instruments():
    r = validate_prose("at 8:30 on Jun 18, the 10-year held its fifth straight session",
                       [])
    assert r.ok  # nothing factual to reject


def test_source_id_token_not_treated_as_number():
    r = validate_prose("yields fell on soft demand (wsj-39)", [])
    assert r.ok  # the '39' in 'wsj-39' must not leak into the number check


def test_validator_strips_cause_with_invented_number():
    nc = NumberCheck()
    ctx = _ctx({"wti": 76.12})
    bad = Cause(claim="oil surged 99 percent on supply fears", cause_source_id="x-1")
    good = Cause(claim="oil traded near 76 dollars", cause_source_id="x-1")
    assert nc.judge(bad, ctx) == Verdict.STRIP
    assert nc.judge(good, ctx) == Verdict.PASS
