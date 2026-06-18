"""New macro metrics: copper + FRED rate series, all optional and graceful-fail.

These verify the metric registry, symbol mapping, FRED units transform, and that
the additions never enter the core health check (spec §7.5 — the banner is core
data / model only). Accuracy stays structural: inflation is FRED's pc1 transform,
not manual YoY math.
"""
from __future__ import annotations

from engine.metrics import (
    METRIC_KEYS,
    METRICS_BY_KEY,
    is_optional,
    is_yield,
)
from sources import fred, prices
from sources.quality import Source, assess
from sources.symbols import CORE_FIELDS, SYMBOLS_BY_METRIC


NEW_KEYS = ("copper", "cpi_yoy", "pce_yoy", "fed_funds", "hy_spread")


def test_new_metrics_registered():
    for key in NEW_KEYS:
        assert key in METRIC_KEYS
        assert key in METRICS_BY_KEY


def test_new_metrics_are_optional_and_non_core():
    # Every addition is optional, so it can never trip the degraded banner.
    for key in NEW_KEYS:
        assert is_optional(key), key
        assert key not in CORE_FIELDS, key


def test_rate_metrics_are_rate_like():
    # The four FRED rate series read in basis points (a delta of a percent level).
    for key in ("cpi_yoy", "pce_yoy", "fed_funds", "hy_spread"):
        assert is_yield(key), key
    # Copper is a price, not rate-like.
    assert not is_yield("copper")


def test_symbol_mapping():
    assert SYMBOLS_BY_METRIC["copper"].yf == "HG=F"
    assert SYMBOLS_BY_METRIC["cpi_yoy"].fred == "CPIAUCSL"
    assert SYMBOLS_BY_METRIC["cpi_yoy"].fred_units == "pc1"
    assert SYMBOLS_BY_METRIC["pce_yoy"].fred_units == "pc1"
    assert SYMBOLS_BY_METRIC["fed_funds"].fred == "DFF"
    assert SYMBOLS_BY_METRIC["hy_spread"].fred == "BAMLH0A0HYM2"
    # FRED-only macro metrics carry no yfinance symbol.
    assert SYMBOLS_BY_METRIC["cpi_yoy"].yf is None


def test_fred_units_passed_to_fetcher():
    captured: dict = {}

    def fetcher(series_id, n, *, units=None):
        captured["series_id"] = series_id
        captured["units"] = units
        return [("2026-05-01", 3.1), ("2026-06-01", 3.2)]

    val = fred.latest_value("CPIAUCSL", fetcher=fetcher, units="pc1")
    assert val == ("2026-06-01", 3.2)
    assert captured["units"] == "pc1"


def test_fred_units_optional_for_plain_fetcher():
    # A 2-arg test fetcher (no units kwarg) still works when units is None.
    def fetcher(series_id, n):
        return [("2026-06-01", 5.33)]

    assert fred.latest_value("DFF", fetcher=fetcher) == ("2026-06-01", 5.33)


def test_units_not_silently_dropped_on_internal_typeerror():
    # A units-aware fetcher that raises TypeError INSIDE its body must NOT be
    # retried without units (that would store a raw CPI index, not the YoY rate).
    # latest_value swallows the exception and returns None (degrade), never a
    # wrong unit-less value (accuracy invariant, spec §1).
    calls: list = []

    def fetcher(series_id, n, *, units=None):
        calls.append(units)
        raise TypeError("simulated internal parse failure")

    assert fred.latest_value("CPIAUCSL", fetcher=fetcher, units="pc1") is None
    # Called exactly once, WITH units — not retried without it.
    assert calls == ["pc1"]


def test_pull_fields_includes_macro_via_injected_fetchers():
    def downloader(symbol, days):
        return [4.10, 4.20, 4.25]  # copper closes

    def series_fetcher(series_id, n, *, units=None):
        # Distinct value per series so we can confirm wiring.
        return [("2026-06-01", {"CPIAUCSL": 3.2, "PCEPI": 2.7,
                                "DFF": 5.33, "BAMLH0A0HYM2": 3.05,
                                "DGS10": 4.43, "DGS2": 4.05}.get(series_id, 1.0))]

    fields = prices.pull_fields(downloader=downloader, series_fetcher=series_fetcher)
    assert fields["copper"].value == 4.25
    assert fields["copper"].source is Source.YFINANCE
    assert fields["cpi_yoy"].value == 3.2
    assert fields["cpi_yoy"].source is Source.FRED
    assert fields["fed_funds"].value == 5.33
    assert fields["hy_spread"].value == 3.05


def test_macro_failure_does_not_trip_banner():
    # All macro metrics missing, all core present -> not degraded, not hard-floored.
    fields = {k: prices._field_from_closes(k, [100.0], Source.YFINANCE)
              for k in CORE_FIELDS}
    for k in NEW_KEYS:
        fields[k] = prices._field_from_closes(k, [], Source.MISSING)
    report = assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.degraded is False
    assert report.hard_floor_tripped is False


def test_fetch_history_routes_macro_to_fred():
    def downloader(symbol, days):
        return [1.0, 2.0]

    def series_fetcher(series_id, n, *, units=None):
        return [("2026-06-01", 3.3), ("2026-06-02", 3.4)]

    hist = prices.fetch_history(20, downloader=downloader, series_fetcher=series_fetcher)
    assert hist["cpi_yoy"] == [3.3, 3.4]
    assert hist["copper"] == [1.0, 2.0]  # copper via yfinance downloader
