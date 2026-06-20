from datetime import date
from marketbrief.sources.yfinance_source import YFinanceSource
from marketbrief.core.protocols import DataSource
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_satisfies_datasource_protocol():
    assert isinstance(YFinanceSource(), DataSource)


def test_fetch_returns_latest_close_per_symbol():
    def fake_dl(symbol, days):
        return [10.0, 11.0, 12.0]  # latest = 12.0
    src = YFinanceSource(downloader=fake_dl)
    result = src.fetch(_ctx())
    assert result.fields["sp500"].value == 12.0
    assert result.fields["sp500"].source == "yfinance"
    assert result.health is SourceHealth.OK


def test_empty_download_yields_missing_field():
    src = YFinanceSource(downloader=lambda s, d: [])
    result = src.fetch(_ctx())
    assert result.fields["sp500"].is_missing


def test_fred_only_metric_absent_from_yfinance_result():
    src = YFinanceSource(downloader=lambda s, d: [5.0])
    result = src.fetch(_ctx())
    assert "cpi_yoy" not in result.fields  # no yf symbol


def test_offline_returns_clean_fields(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    result = YFinanceSource().fetch(_ctx())
    assert result.fields["sp500"].is_usable
