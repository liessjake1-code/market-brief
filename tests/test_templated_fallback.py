"""Redesign: the cause-free computed fallback is substantive, never bare or invented.

`computed_section_line` builds the spec §5.6 four-ingredient read MINUS the causal
"why" (level-in-context, the move, the streak/range, a forward hook) from numbers
and rolling history. It must never assert a cause (CLAUDE.md / spec §2) and must
degrade to the plain line when data is stale or missing.
"""

from __future__ import annotations

from render import templated
from sources.quality import Field, Source


def _field(metric: str, value: float, *, stale: bool = False) -> Field:
    return Field(metric, value, Source.YFINANCE, stale=stale)


def test_quiet_section_is_substantive_not_bare():
    # A rising series with no break/streak still reads level + move + hook.
    hist = [6400.0, 6410.0, 6420.0, 6431.0]
    line = templated.computed_section_line(_field("sp500", 6431.0), hist, section_id="us_equities")
    assert "S&P 500 at 6,431" in line
    assert "higher" in line
    assert "No clear catalyst flagged." in line
    assert "breadth confirms" in line  # the forward hook


def test_never_asserts_a_cause():
    hist = [100.0, 101.0, 102.0]
    line = templated.computed_section_line(_field("wti", 102.0), hist, section_id="commodities")
    # No causal connective; "no clear catalyst" is the honest read (spec §2).
    for banned in (" because ", " after the ", " on a ", " driven by "):
        assert banned not in line
    assert "No clear catalyst flagged." in line


def test_new_high_is_called_out_as_level_in_context():
    hist = [10.0] * 20 + [99.0]  # a clear new high
    line = templated.computed_section_line(_field("vix", 99.0), hist, section_id="volatility_breadth")
    assert "high" in line


def test_stale_field_degrades_to_plain_line():
    line = templated.computed_section_line(
        _field("gold", 4200.0, stale=True), [4100.0, 4200.0], section_id="commodities",
    )
    assert "stale" in line  # the plain templated_line stale path, not the rich read


def test_missing_field_degrades_to_plain_line():
    line = templated.computed_section_line(
        Field("dxy", None, Source.MISSING), [], section_id="rates_and_dollar",
    )
    assert "data unavailable" in line


def test_yield_move_reads_in_bps():
    hist = [4.30, 4.43]  # +13 bps
    line = templated.computed_section_line(_field("ust10y", 4.43), hist, section_id="rates_and_dollar")
    assert "bps" in line
    assert "swing factor" in line  # rates forward hook


def test_section_with_cause_joins_accurate_numbers_and_model_why():
    # The numbers sentence is 100% Python (accurate); the model's number-free cause
    # is appended verbatim, capitalized and terminated.
    hist = [6400.0, 6410.0, 6431.0]
    line = templated.section_with_cause(
        _field("sp500", 6431.0), hist, "stocks rose after the trade deal")
    assert line.startswith("S&P 500 at 6,431")          # accurate computed head
    assert "Stocks rose after the trade deal." in line   # model cause, cleaned


def test_section_with_cause_empty_cause_is_just_numbers():
    hist = [6400.0, 6431.0]
    line = templated.section_with_cause(_field("sp500", 6431.0), hist, "")
    assert line.startswith("S&P 500 at 6,431")
    assert line.endswith(".")
