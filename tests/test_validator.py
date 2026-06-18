"""Phase 6 — tolerant number validator (spec §5.6; Part 4.4; roadmap §6.7 gate).

This is the load-bearing trust mechanism: an invented number must fail to ship,
while normal rounded prose must pass. An exact-match check would collapse the
brief into templates daily, so the tolerance is mandatory and tested both ways.
"""

from __future__ import annotations

from engine.validator import DEFAULT_TOLERANCE_PCT, validate_prose


# --- accepts legitimate rounded / approximated prose ---------------------- #
def test_accepts_rounded_price():
    # Input 76.23; the model wrote "about 76 dollars".
    r = validate_prose("Crude settled at about 76 dollars.", [76.23])
    assert r.ok, r.rejected


def test_accepts_rounded_percentage_within_tolerance():
    # Input 0.39%; prose says "0.4%".
    r = validate_prose("The S&P rose 0.4%.", [0.39])
    assert r.ok, r.rejected


def test_accepts_bps_within_one_bp():
    r = validate_prose("The 10-year added 8 bps.", [8.4])
    assert r.ok, r.rejected


def test_accepts_derived_figure_present_in_input_set():
    # 2s10s spread is a derived figure; if it's in the inputs, prose may cite it.
    r = validate_prose("The 2s10s spread sits near -43 bps.", [4.28, 4.71, -43.0])
    assert r.ok, r.rejected


def test_accepts_large_index_level_with_thousands_separator():
    r = validate_prose("The Dow closed near 38,900.", [38900.0])
    assert r.ok, r.rejected


# --- rejects invented numbers --------------------------------------------- #
def test_rejects_invented_number():
    # 91 appears nowhere in the inputs.
    r = validate_prose("Crude jumped to 91 dollars on the news.", [76.2, 78.5])
    assert not r.ok
    assert any("91" in tok for tok in r.rejected)


def test_rejects_derived_figure_absent_from_input_set():
    # The model asserts a weekly sum that was NOT pre-computed -> invented.
    r = validate_prose("Yields are up 12 bps on the week.", [4.28, 4.20])
    assert not r.ok


def test_rejects_percentage_outside_tolerance():
    # Input 0.39%; prose claims 1.5% -> outside ±0.05 and not a rounding of 0.39.
    r = validate_prose("The S&P rose 1.5%.", [0.39])
    assert not r.ok


# --- whitelist: times, dates, ordinals skipped ---------------------------- #
def test_clock_time_is_whitelisted():
    r = validate_prose("Pre-market as of 8:25 CT, futures were firm.", [])
    assert r.ok, r.rejected


def test_iso_date_is_whitelisted():
    r = validate_prose("On 2026-06-17 the Fed met.", [])
    assert r.ok


def test_spelled_and_digit_ordinals_whitelisted():
    r = validate_prose("It was the 5th straight session higher.", [])
    assert r.ok


def test_month_day_date_whitelisted():
    r = validate_prose("CPI lands Jun 10 this month.", [])
    assert r.ok


# --- the retry signal ----------------------------------------------------- #
def test_rejected_list_drives_retry_then_template():
    r = validate_prose("Crude near 76, gold near 9999.", [76.2, 2330.0])
    assert not r.ok
    # The caller retries once on a non-empty rejected list, then templates.
    assert "9999" in " ".join(r.rejected)


def test_instrument_names_not_treated_as_data():
    # "10-year", "2s10s", "S&P 500" are names; only the real claim (4.46%) checks.
    r = validate_prose("The 10-year yield is 4.46% and the 2s10s spread narrowed.",
                       [4.46, -25.0])
    assert r.ok, r.rejected


def test_real_index_level_still_validated_despite_name_whitelist():
    # Whitelisting the NAME "S&P 500" must not whitelist a real LEVEL claim.
    r = validate_prose("The S&P 500 closed at 7,420.", [7420.0])
    assert r.ok, r.rejected
    # An invented level must still be caught.
    bad = validate_prose("The S&P 500 closed at 8,888.", [7420.0])
    assert not bad.ok


def test_negative_numbers_handled():
    r = validate_prose("The spread is -43 bps.", [-43.0])
    assert r.ok


def test_tolerance_is_configurable():
    # With a wide tolerance, 0.45 vs input 0.39 should pass.
    r = validate_prose("Up 0.45%.", [0.39], tolerance_pct=0.10)
    assert r.ok
    # With the default tight band it should not (0.45 vs 0.39 = 0.06 > 0.05,
    # and rounding 0.45->0.5 != 0.39->0.4).
    r2 = validate_prose("Up 0.45%.", [0.39], tolerance_pct=DEFAULT_TOLERANCE_PCT)
    assert not r2.ok
