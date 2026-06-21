from marketbrief.core.enums import Direction, ChartKind
from marketbrief.core.models import (
    FigureCell, StatRow, WhyLine, ChartRef, GlanceRow, MoverRow, SparkRef,
    SectionVM, LiveSnapshot, BriefView, MoverPeriod, MoverBoard,
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


def _mover(ticker, value, direction):
    return MoverRow(ticker=ticker, favicon_url=None, value_str=value,
                    direction=direction, why="")


def test_mover_board_defaults_empty_and_has_no_rows():
    board = MoverBoard()
    assert board.periods == []
    assert board.has_rows is False


def test_mover_board_has_rows_true_when_any_period_populated():
    day = MoverPeriod(label="Day", winners=[_mover("NVDA", "+4.8%", Direction.UP)],
                      losers=[_mover("PFE", "-3.4%", Direction.DOWN)])
    board = MoverBoard(periods=[day, MoverPeriod(label="Week")])
    assert board.has_rows is True
    assert board.periods[0].winners[0].ticker == "NVDA"


def test_mover_board_empty_periods_have_no_rows():
    board = MoverBoard(periods=[MoverPeriod(label="Day"), MoverPeriod(label="Week")])
    assert board.has_rows is False


def test_sectionvm_mover_board_defaults_none():
    lead = WhyLine(text="No movers.", hedged=True)
    s = SectionVM(id="movers", title="Movers", order=5, quiet=True, lead=lead)
    assert s.mover_board is None


def test_mover_board_is_frozen():
    import pytest
    board = MoverBoard()
    with pytest.raises(Exception):
        board.periods = [MoverPeriod(label="Day")]
