from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
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
