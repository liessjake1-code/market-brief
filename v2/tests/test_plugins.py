from datetime import date
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.protocols import DataSource, Section
from marketbrief.sections.equities import EquitiesSection


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_equities_satisfies_section_protocol():
    assert isinstance(EquitiesSection(), Section)


def test_equities_builds_a_vm():
    vm = EquitiesSection().build(_ctx())
    assert vm is not None
    assert vm.id == "us_equities"
