from marketbrief.core.config import Config
from marketbrief.core.models import Field, ComputedNumbers
from marketbrief.compute.derive import derive_numbers

CFG = Config()


def _f(metric, value, *, source="yfinance", stale=False):
    return Field(metric=metric, value=value, source=source, stale=stale)


def test_usable_values_included():
    resolved = {"ust10y": _f("ust10y", 4.25), "wti": _f("wti", 76.1)}
    out = derive_numbers(resolved, CFG)
    assert isinstance(out, ComputedNumbers)
    assert out.values["ust10y"] == 4.25
    assert out.values["wti"] == 76.1


def test_missing_or_stale_field_excluded():
    resolved = {
        "ust10y": _f("ust10y", None, source="missing"),
        "wti": _f("wti", 76.1, stale=True),
    }
    out = derive_numbers(resolved, CFG)
    assert "ust10y" not in out.values
    assert "wti" not in out.values


def test_2s10s_spread_when_both_legs_present():
    resolved = {"ust10y": _f("ust10y", 4.25), "ust2y": _f("ust2y", 3.85)}
    out = derive_numbers(resolved, CFG)
    assert round(out.values["spread_2s10s"], 2) == 0.40


def test_2s10s_absent_when_a_leg_missing():
    resolved = {"ust10y": _f("ust10y", 4.25)}
    out = derive_numbers(resolved, CFG)
    assert "spread_2s10s" not in out.values


def test_history_derived_figures_absent():
    # No rolling history in #3: nothing like *_5d_high / *_streak appears.
    resolved = {"ust10y": _f("ust10y", 4.25)}
    out = derive_numbers(resolved, CFG)
    assert not any("_5d" in k or "_20d" in k or "streak" in k for k in out.values)
