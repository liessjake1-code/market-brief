from marketbrief.core.enums import Direction
from marketbrief.core.models import Field
from marketbrief.render.source_links import source_url, favicon_url, yahoo_ticker_url, safe_url
from marketbrief.sections._format import (
    figure_cell, direction_of, quiet_lead, METRIC_LABELS, QUIET_LINES,
)


def test_source_url_yield_is_fred():
    assert "fred.stlouisfed.org" in source_url("ust10y")


def test_source_url_index_is_yahoo():
    assert "finance.yahoo.com" in source_url("sp500")


def test_source_url_fred_only_metric_is_fred():
    assert "fred.stlouisfed.org" in source_url("cpi_yoy")


def test_source_url_unknown_is_none():
    assert source_url("not_a_metric") is None


def test_favicon_none_domain():
    assert favicon_url(None) is None


def test_direction_of():
    assert direction_of(0.4) is Direction.UP
    assert direction_of(-0.4) is Direction.DOWN
    assert direction_of(0.0) is Direction.FLAT
    assert direction_of(None) is Direction.FLAT


def test_figure_cell_stale_flag_propagates():
    f = Field(metric="sp500", value=5000.0, source="yfinance", stale=True)
    cell = figure_cell("sp500", f)
    assert cell.stale is True
    assert cell.metric_label == "S&P"
    assert "finance.yahoo.com" in cell.source_url


def test_safe_url_rejects_javascript_scheme():
    assert safe_url("javascript:alert(1)") is None


def test_safe_url_rejects_data_scheme():
    assert safe_url("data:text/html,<h1>xss</h1>") is None


def test_safe_url_accepts_https():
    url = "https://finance.yahoo.com/quote/%5EGSPC"
    assert safe_url(url) == url


def test_safe_url_accepts_http():
    url = "http://example.com"
    assert safe_url(url) == url


def test_safe_url_handles_none():
    assert safe_url(None) is None


def test_quiet_lead_is_hedged_and_sourceless():
    w = quiet_lead("us_equities")
    assert w.hedged is True and w.source_url is None
    assert "no clear catalyst" in w.text.lower()
