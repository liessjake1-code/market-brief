from datetime import date
from marketbrief.sources.fred_source import FredSource
from marketbrief.core.protocols import DataSource
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_satisfies_datasource_protocol():
    assert isinstance(FredSource(), DataSource)


def test_fetch_returns_latest_observation_with_as_of():
    def fake(series_id, limit, units=None):
        return [("2026-06-18", 4.1), ("2026-06-19", 4.2)]  # oldest->newest
    src = FredSource(series_fetcher=fake)
    result = src.fetch(_ctx())
    assert result.fields["ust10y"].value == 4.2
    assert result.fields["ust10y"].source == "fred"
    assert result.fields["ust10y"].as_of == "2026-06-19"


def test_units_transform_is_passed_through():
    seen = {}
    def fake(series_id, limit, units=None):
        seen[series_id] = units
        return [("2026-05-01", 3.2)]
    FredSource(series_fetcher=fake).fetch(_ctx())
    assert seen["CPIAUCSL"] == "pc1"  # YoY inflation transform preserved


def test_only_fred_metrics_present():
    src = FredSource(series_fetcher=lambda s, l, units=None: [("2026-06-19", 1.0)])
    result = src.fetch(_ctx())
    assert "ust10y" in result.fields
    assert "vix" not in result.fields  # no fred series


def test_fetcher_failure_degrades_to_failed_health():
    def boom(series_id, limit, units=None):
        raise RuntimeError("FRED down")
    result = FredSource(series_fetcher=boom).fetch(_ctx())
    assert result.health is SourceHealth.FAILED


def test_offline_returns_clean_fields(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    result = FredSource().fetch(_ctx())
    assert result.fields["ust10y"].is_usable


def test_real_fetcher_does_not_leak_api_key_in_error(monkeypatch):
    import requests
    from marketbrief.sources import fred_source

    monkeypatch.setenv("FRED_API_KEY", "SECRET_KEY_123")

    class _Resp:
        status_code = 403
        url = "https://api.stlouisfed.org/fred/series/observations?api_key=SECRET_KEY_123"

    def boom(*args, **kwargs):
        err = requests.HTTPError("403 Client Error: url=" + _Resp.url)
        err.response = _Resp()
        raise err

    monkeypatch.setattr(requests, "get", boom)
    try:
        fred_source._real_series_fetcher("DGS10", 5)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "SECRET_KEY_123" not in str(exc)
        assert exc.__cause__ is None  # original (URL-bearing) chain suppressed
