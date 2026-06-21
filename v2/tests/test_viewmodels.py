from marketbrief.core.enums import Direction, ChartKind
from marketbrief.core.models import (
    FigureCell, StatRow, WhyLine, ChartRef, GlanceRow, MoverRow, SparkRef,
    SectionVM, LiveSnapshot, BriefView,
)


def test_figurecell_defaults():
    c = FigureCell(metric_label="S&P", value_str="5,000", change_str="+0.4%",
                   direction=Direction.UP)
    assert c.stale is False and c.mechanical is False and c.source_url is None


def test_sectionvm_enriched_shape():
    lead = WhyLine(text="Indices little changed; no clear catalyst.", hedged=True)
    s = SectionVM(id="us_equities", title="US Equities", order=1, quiet=True, lead=lead)
    assert s.stat_rows == [] and s.why_lines == [] and s.is_promoted is False


def test_models_are_frozen():
    c = FigureCell(metric_label="x", value_str="1", change_str="0", direction=Direction.FLAT)
    import pytest
    with pytest.raises(Exception):
        c.stale = True


def test_briefview_compose():
    bv = BriefView(diff_line="Markets little changed overnight.", glance_rows=[],
                   sections=[], live=None, degraded=False, banner_text=None)
    assert bv.live is None and bv.degraded is False
