from datetime import date
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.protocols import DataSource, Section
from marketbrief.sources.placeholder import PlaceholderSource
from marketbrief.sections.summary import SummarySection
from marketbrief.core.health import CORE_FIELDS


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_placeholder_satisfies_datasource_protocol():
    assert isinstance(PlaceholderSource(), DataSource)


def test_placeholder_returns_all_core_fields():
    result = PlaceholderSource().fetch(_ctx())
    for k in CORE_FIELDS:
        assert k in result.fields
        assert result.fields[k].is_usable


def test_summary_satisfies_section_protocol():
    assert isinstance(SummarySection(), Section)


def test_summary_builds_a_vm():
    vm = SummarySection().build(_ctx())
    assert vm is not None
    assert vm.id == "summary"
