from datetime import date
from marketbrief.sources.stooq_source import StooqSource
from marketbrief.core.protocols import DataSource
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_satisfies_datasource_protocol():
    assert isinstance(StooqSource(), DataSource)


def test_fetch_returns_latest_close_for_mapped_symbols():
    src = StooqSource(downloader=lambda s, d: [4990.0, 5000.0])
    result = src.fetch(_ctx())
    assert result.fields["sp500"].value == 5000.0
    assert result.fields["sp500"].source == "stooq"


def test_unmapped_metric_absent():
    src = StooqSource(downloader=lambda s, d: [1.0])
    result = src.fetch(_ctx())
    assert "vix" not in result.fields  # no stooq symbol mapped


def test_failure_yields_missing_not_raise():
    src = StooqSource(downloader=lambda s, d: [])
    result = src.fetch(_ctx())
    assert result.fields["sp500"].is_missing
    assert result.health is SourceHealth.OK  # best-effort, still returns


def test_offline_returns_clean_fields(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    result = StooqSource().fetch(_ctx())
    assert result.fields["sp500"].is_usable
