from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Field, NarratedWhy, Cause
from marketbrief.sections.equities import EquitiesSection


def _ctx(fields, narration=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), resolved_fields=fields,
                        narration=narration or {})


def test_quiet_when_no_fields():
    vm = EquitiesSection().build(_ctx({}))
    assert vm.id == "us_equities" and vm.quiet is True
    assert "no clear catalyst" in vm.lead.text.lower()
    assert vm.stat_rows == []


def test_full_read_with_fields_and_narration():
    fields = {"sp500": Field(metric="sp500", value=5000.0, source="yfinance"),
              "nasdaq": Field(metric="nasdaq", value=16000.0, source="yfinance")}
    nar = {"us_equities": NarratedWhy(
        section_id="us_equities", text="Stocks rose on soft inflation.",
        causes=[Cause(claim="Stocks rose on soft inflation.",
                      cause_source_id="art1", verdict=Verdict.PASS)])}
    vm = EquitiesSection().build(_ctx(fields, nar))
    assert vm.quiet is False
    assert len(vm.stat_rows[0].cells) == 2
    assert vm.lead.text == "Stocks rose on soft inflation."
    assert vm.lead.hedged is False


def test_stale_field_marked_in_cell():
    fields = {"sp500": Field(metric="sp500", value=5000.0, source="yfinance", stale=True)}
    vm = EquitiesSection().build(_ctx(fields))
    assert vm.stat_rows[0].cells[0].stale is True
