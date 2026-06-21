from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Field, NarratedWhy, Cause
from marketbrief.sections.washington import WashingtonSection
from marketbrief.sections.economic_data import EconomicDataSection
from marketbrief.sections.earnings import EarningsSection
from marketbrief.sections.what_to_watch import WhatToWatchSection


def _ctx(narration=None, fields=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), narration=narration or {},
                        resolved_fields=fields or {})


def test_washington_quiet():
    vm = WashingtonSection().build(_ctx())
    assert vm.id == "washington" and vm.quiet is True
    assert "no market-moving policy" in vm.lead.text.lower()


def test_washington_with_narration():
    nar = {"washington": NarratedWhy(section_id="washington", text="Fed held rates.",
            causes=[Cause(claim="Fed held rates.", cause_source_id="art2", verdict=Verdict.PASS)])}
    vm = WashingtonSection().build(_ctx(nar))
    assert vm.quiet is False and vm.lead.text == "Fed held rates."


def test_econ_data_rows_when_fields_present():
    fields = {"cpi_yoy": Field(metric="cpi_yoy", value=3.1, source="fred")}
    vm = EconomicDataSection().build(_ctx(fields=fields))
    assert vm.id == "economic_data_scorecard"
    assert len(vm.stat_rows[0].cells) == 1


def test_earnings_quiet():
    assert EarningsSection().build(_ctx()).quiet is True


def test_what_to_watch_quiet():
    assert WhatToWatchSection().build(_ctx()).quiet is True
