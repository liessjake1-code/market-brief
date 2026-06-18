"""Phase 4 — Top Story engine (spec §5, §5.1, §7.7; roadmap §4.11 gate).

Gate: every priority branch returns the right Top Story on fixtures; a mechanical
date is annotated-not-promoted; a flat day reads "quiet tape". Uses the real,
source-verified data files (FOMC 2026-06-17, witching 2026-06-18, Russell recon
2026-06-26) so the loader is exercised against actual data.
"""

from __future__ import annotations

from datetime import date

from engine import top_story as TS
from engine.calendars import mechanical_metrics_for, tier_one_for
from engine.metrics import METRIC_KEYS
from engine.state import State

# A quiet, non-event weekday with no tier-one event or mechanical move.
QUIET_DAY = date(2026, 6, 22)        # a Monday, nothing on either calendar
FOMC_DAY = date(2026, 6, 17)         # FOMC decision (sep day) in tier_one_calendar
WITCHING_DAY = date(2026, 6, 18)     # quad witching (us_equities, volatility_breadth)
RUSSELL_DAY = date(2026, 6, 26)      # Russell reconstitution (us_equities)


def _flat_state() -> State:
    metrics = {k: {"history": [100.0] * 25} for k in METRIC_KEYS}
    return State(data={"metrics": metrics}, path="<test>")


def _state_with(key: str, history: list[float]) -> State:
    metrics = {k: {"history": [100.0] * 25} for k in METRIC_KEYS}
    metrics[key] = {"history": history}
    return State(data={"metrics": metrics}, path="<test>")


# --- data-file loaders work against the real files ------------------------ #
def test_real_calendar_loads_fomc():
    hit = tier_one_for(FOMC_DAY)
    assert hit is not None
    assert hit.category == "fomc"
    assert hit.promotes == "washington"
    assert hit.sep is True


def test_real_mechanical_loads_witching():
    m = mechanical_metrics_for(WITCHING_DAY)
    assert "sp500" in m and "vix" in m


def test_quiet_day_has_no_calendar_hits():
    assert tier_one_for(QUIET_DAY) is None
    assert mechanical_metrics_for(QUIET_DAY) == set()


# --- Step 1: tier-one promotion ------------------------------------------- #
def test_tier_one_fomc_promotes_washington():
    d = TS.decide(_flat_state(), day=FOMC_DAY)
    assert d.reason == "tier_one"
    assert d.section == "washington"
    assert d.order[0] == "washington"
    assert d.tier_one_category == "fomc"


def test_tier_one_outranks_a_large_move():
    # Even with a huge S&P move, a tier-one day wins (step 1 before step 2).
    st = _state_with("sp500", [100.0] * 24 + [110.0])  # +10% move
    d = TS.decide(st, day=FOMC_DAY)
    assert d.reason == "tier_one"
    assert d.section == "washington"


# --- Step 2: large move, z-score tie-break -------------------------------- #
def test_large_sp500_move_promotes_equities():
    # Gentle prior moves, then a big jump that clears the >1% floor.
    hist = [100.0 + 0.05 * i for i in range(24)] + [115.0]
    st = _state_with("sp500", hist)
    d = TS.decide(st, day=QUIET_DAY)
    assert d.reason == "large_move"
    assert d.section == "us_equities"


def test_zscore_tiebreak_picks_largest_standardized_not_raw():
    """Two metrics clear their floors; the larger z-score wins, not larger raw %."""
    # VIX: calm history then +20% (clears >15% floor), modest z given its own vol.
    vix_hist = [13.0 + 0.01 * i for i in range(24)] + [16.0]
    # WTI: very calm history then +3.5% (clears >3%), which is a HUGE z vs its own std.
    wti_hist = [70.0 + 0.001 * i for i in range(24)] + [72.5]
    metrics = {k: {"history": [100.0] * 25} for k in METRIC_KEYS}
    metrics["vix"] = {"history": vix_hist}
    metrics["wti"] = {"history": wti_hist}
    st = State(data={"metrics": metrics}, path="<test>")
    d = TS.decide(st, day=QUIET_DAY)
    assert d.reason == "large_move"
    # WTI's move is tiny in raw % vs VIX's 20%, but enormous in z-score terms.
    assert d.section == "commodities"


def test_below_floor_does_not_promote():
    # A 0.5% S&P move does not clear the >1% floor.
    hist = [100.0] * 24 + [100.5]
    st = _state_with("sp500", hist)
    d = TS.decide(st, day=QUIET_DAY)
    assert d.reason == "quiet_tape"


# --- Mechanical guard: annotate, do not promote --------------------------- #
def test_mechanical_date_suppresses_promotion():
    # Big S&P move ON the Russell reconstitution day -> annotated, not promoted.
    hist = [100.0] * 24 + [115.0]
    st = _state_with("sp500", hist)
    d = TS.decide(st, day=RUSSELL_DAY)
    assert d.reason == "quiet_tape"          # promotion suppressed
    assert "sp500" in d.mechanical_notes
    assert "mechanical" in d.mechanical_notes["sp500"]


def test_mechanical_guard_only_affects_listed_metrics():
    # On witching day, WTI is NOT affected; a big WTI move still promotes.
    # Realistic small prior moves (non-zero std) then a jump clearing >3%.
    hist = [70.0 + 0.02 * i for i in range(24)] + [75.0]
    st = _state_with("wti", hist)
    d = TS.decide(st, day=WITCHING_DAY)
    assert d.reason == "large_move"
    assert d.section == "commodities"


# --- Step 3: quiet tape + ordering ---------------------------------------- #
def test_quiet_tape_on_flat_day():
    d = TS.decide(_flat_state(), day=QUIET_DAY)
    assert d.reason == "quiet_tape"
    assert d.section == "us_equities"
    assert d.order == list(TS.FALLBACK_ORDER)


def test_stale_metric_excluded_from_engine():
    hist = [100.0] * 24 + [115.0]
    st = _state_with("sp500", hist)
    d = TS.decide(st, day=QUIET_DAY, stale_keys={"sp500"})
    assert d.reason == "quiet_tape"  # the only mover was stale -> excluded


def test_floating_slot_pulls_section_out_of_fallback():
    st = _state_with("sp500", [100.0] * 24 + [115.0])
    d = TS.decide(st, day=QUIET_DAY)
    # Promoted section appears exactly once, at the front.
    assert d.order[0] == "us_equities"
    assert d.order.count("us_equities") == 1
    assert set(d.order) == set(TS.FALLBACK_ORDER)
