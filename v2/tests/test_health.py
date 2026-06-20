from marketbrief.core.health import assess, CORE_FIELDS
from marketbrief.core.models import Field


def _all_ok() -> dict[str, Field]:
    return {k: Field(metric=k, value=1.0, source="yfinance") for k in CORE_FIELDS}


def test_clean_data_no_degrade_no_floor():
    report = assess(_all_ok(), degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.degraded is False
    assert report.hard_floor_tripped is False


def test_two_stale_core_trips_degrade():
    fields = _all_ok()
    fields["sp500"] = Field(metric="sp500", value=1.0, source="yfinance", stale=True)
    fields["wti"] = Field(metric="wti", value=1.0, source="yfinance", stale=True)
    report = assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.degraded is True
    assert report.hard_floor_tripped is False


def test_five_missing_core_trips_hard_floor():
    fields = _all_ok()
    for k in ("sp500", "nasdaq", "dow", "russell", "ust10y"):
        fields[k] = Field(metric=k, value=None, source="missing")
    report = assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.hard_floor_tripped is True


def test_model_failure_alone_trips_degrade():
    report = assess(_all_ok(), degraded_stale_threshold=2, hard_floor_missing_threshold=4, model_failed=True)
    assert report.degraded is True
