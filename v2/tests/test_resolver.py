from marketbrief.fetch.resolver import resolve_fields
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.config import Config


def _sr(name, fields):
    return SourceResult(name=name, fields=fields, health=SourceHealth.OK)


def test_yield_prefers_fred_over_yfinance():
    per = {
        "fred": _sr("fred", {"ust10y": Field(metric="ust10y", value=4.2, source="fred", as_of="2026-06-19")}),
        "yfinance": _sr("yfinance", {"ust10y": Field(metric="ust10y", value=4.1, source="yfinance")}),
    }
    out = resolve_fields(per, Config())
    assert out["ust10y"].value == 4.2
    assert out["ust10y"].source == "fred"


def test_yield_falls_back_to_yfinance_when_fred_missing():
    per = {"yfinance": _sr("yfinance", {"ust10y": Field(metric="ust10y", value=4.1, source="yfinance")})}
    out = resolve_fields(per, Config())
    assert out["ust10y"].value == 4.1
    assert out["ust10y"].source == "yfinance"


def test_oil_prefers_yfinance():
    per = {"yfinance": _sr("yfinance", {"wti": Field(metric="wti", value=80.0, source="yfinance")})}
    out = resolve_fields(per, Config())
    assert out["wti"].value == 80.0
    assert out["wti"].source == "yfinance"
    assert out["wti"].stale is False


def test_oil_missing_yfinance_uses_fred_as_dated_last_resort_stale():
    per = {"fred": _sr("fred", {"wti": Field(metric="wti", value=78.0, source="fred", as_of="2026-06-16")})}
    out = resolve_fields(per, Config())
    assert out["wti"].source == "fred_last_resort"
    assert out["wti"].stale is True
    assert out["wti"].as_of == "2026-06-16"
    assert out["wti"].note


def test_oil_missing_everywhere_is_missing_and_stale():
    out = resolve_fields({}, Config())
    assert out["wti"].is_missing
    assert out["wti"].stale is True


def test_index_falls_back_to_stooq_when_yfinance_missing():
    per = {"stooq": _sr("stooq", {"sp500": Field(metric="sp500", value=5000.0, source="stooq")})}
    out = resolve_fields(per, Config())
    assert out["sp500"].value == 5000.0
    assert out["sp500"].source == "stooq"


def test_index_prefers_yfinance_over_stooq():
    per = {
        "yfinance": _sr("yfinance", {"sp500": Field(metric="sp500", value=5001.0, source="yfinance")}),
        "stooq": _sr("stooq", {"sp500": Field(metric="sp500", value=5000.0, source="stooq")}),
    }
    out = resolve_fields(per, Config())
    assert out["sp500"].source == "yfinance"


def test_metric_absent_everywhere_is_missing():
    out = resolve_fields({}, Config())
    assert out["sp500"].is_missing
    assert out["sp500"].source == "missing"


def test_resolver_covers_every_symbol():
    out = resolve_fields({}, Config())
    from marketbrief.core.symbols import SYMBOLS_BY_METRIC
    for k in SYMBOLS_BY_METRIC:
        assert k in out
