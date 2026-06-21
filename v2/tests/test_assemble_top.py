from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Direction
from marketbrief.core.models import Field
from marketbrief.assemble.diff_line import build_diff_line
from marketbrief.assemble.glance import build_glance_rows


def _ctx(fields=None, prev=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), resolved_fields=fields or {}, prev_state=prev or {})


def test_diff_line_no_prior_state():
    assert build_diff_line(_ctx()) == "Markets little changed overnight."


def test_diff_line_excludes_stale():
    fields = {"sp500": Field(metric="sp500", value=5100.0, source="yfinance", stale=True)}
    prev = {"fields": {"sp500": 5000.0}}
    # stale field cannot drive the diff line
    assert build_diff_line(_ctx(fields, prev)) == "Markets little changed overnight."


def test_diff_line_reports_move():
    fields = {"sp500": Field(metric="sp500", value=5100.0, source="yfinance")}
    prev = {"fields": {"sp500": 5000.0}}
    line = build_diff_line(_ctx(fields, prev))
    assert "S&P" in line and "%" in line


def test_glance_has_live_row():
    rows = build_glance_rows(_ctx(), sections=[])
    live = [r for r in rows if r.is_live]
    assert len(live) == 1 and "morning" in live[0].category.lower()


def _section_with_cells(sid, label, pairs):
    from marketbrief.core.models import SectionVM, StatRow, FigureCell, WhyLine
    cells = [FigureCell(metric_label=m, value_str=v, change_str="", direction=Direction.FLAT)
             for m, v in pairs]
    return SectionVM(id=sid, title=label, order=1, quiet=False,
                     lead=WhyLine(text="Stocks rose on soft inflation.", hedged=False),
                     stat_rows=[StatRow(label=label, cells=cells)])


def test_glance_numbers_carry_their_metric_labels():
    # Each figure must be labeled (S&P 5,000) so the reader knows which number is which.
    sec = _section_with_cells("us_equities", "Indices",
                              [("S&P", "5,000"), ("Nasdaq", "18,000")])
    rows = build_glance_rows(_ctx(), sections=[sec])
    markets = next(r for r in rows if r.category == "Markets")
    assert "S&P 5,000" in markets.latest
    assert "Nasdaq 18,000" in markets.latest
    # bare, label-less numbers must not appear
    assert markets.latest.count("5,000") == 1


def test_glance_carries_no_explanation():
    # At a Glance is numbers only; the "why" lives in each section, not here.
    sec = _section_with_cells("us_equities", "Indices", [("S&P", "5,000")])
    rows = build_glance_rows(_ctx(), sections=[sec])
    markets = next(r for r in rows if r.category == "Markets")
    assert markets.why_brief == ""
    # the section's lead text must not leak into the glance row
    assert "soft inflation" not in markets.latest
