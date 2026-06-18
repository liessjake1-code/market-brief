"""Phase 3 — diff line (spec §4.1, §5.5; roadmap §3.8 gate).

Gate: diff line correct against fixtures including post-holiday gap; degrades to
silence (not wrong deltas) on thin history; quiet tape when nothing clears.
"""

from __future__ import annotations

from engine import diff as D
from engine.metrics import METRIC_KEYS
from engine.state import State


def _state(histories: dict[str, list[float]]) -> State:
    metrics = {k: {"history": list(histories.get(k, []))} for k in METRIC_KEYS}
    return State(data={"metrics": metrics}, path="<test>")


# --- detectors ------------------------------------------------------------ #
def test_detect_flip_up_then_down():
    # deltas: +,+,- => last move flips to lower
    assert D.detect_flip([100, 101, 102, 101]) == "turned lower"


def test_detect_flip_needs_three_points():
    assert D.detect_flip([100, 101]) is None


def test_detect_flip_none_when_same_direction():
    assert D.detect_flip([100, 101, 102, 103]) is None


def test_detect_break_new_high():
    assert "5-day high" in (D.detect_break([10, 11, 12, 13, 14, 20], 5) or "")


def test_detect_break_new_low():
    assert "5-day low" in (D.detect_break([20, 19, 18, 17, 16, 5], 5) or "")


def test_detect_break_none_inside_range():
    assert D.detect_break([10, 20, 15, 12, 18, 16], 5) is None


def test_detect_break_thin_history_is_none():
    assert D.detect_break([10, 11], 5) is None


def test_detect_streak_counts_consecutive():
    # 4 rising deltas
    res = D.detect_streak([10, 11, 12, 13, 14])
    assert res == (4, "higher")


def test_detect_streak_below_min_is_none():
    assert D.detect_streak([10, 11, 12]) is None  # only 2 deltas < MIN_STREAK


# --- assembly ------------------------------------------------------------- #
def test_quiet_tape_when_nothing_clears():
    st = _state({"sp500": [100.0, 100.0, 100.0]})  # flat, no signal
    res = D.compute_diff(st)
    assert res.quiet is True
    assert "Quiet tape" in res.line


def test_thin_history_degrades_to_silence_not_wrong_delta():
    st = _state({"sp500": [100.0]})  # one point only
    res = D.compute_diff(st)
    assert res.quiet is True
    assert res.events == []


def test_break_high_is_reported_and_reframes():
    st = _state({"sp500": [10, 11, 12, 13, 14, 25]})  # new 5-day high
    res = D.compute_diff(st)
    assert res.has_signal
    assert any(e.kind == "break_high" for e in res.events)
    assert "S&P 500" in res.line


def test_20day_break_outranks_5day_break_as_reframing():
    # 22 closes, last is a 20-day high (and a 5-day high). 20-day should reframe.
    hist = [10 + i for i in range(21)] + [100.0]
    st = _state({"sp500": hist})
    res = D.compute_diff(st)
    assert res.reframing_event is not None
    assert "20-day high" in res.reframing_event.text


def test_stale_metric_excluded_from_diff():
    st = _state({"sp500": [10, 11, 12, 13, 14, 25]})
    res = D.compute_diff(st, stale_keys={"sp500"})
    assert res.quiet is True  # the only signal was stale -> excluded


def test_post_holiday_gap_uses_last_session_not_calendar():
    """A 3-day calendar gap must still compare to the last real close.

    The diff is computed purely off history order, so the gap is invisible to it;
    the latest close is "yesterday" regardless of calendar days elapsed (§5.5).
    """
    st = _state({"sp500": [10, 11, 12, 13, 14, 13]})  # flip to lower on last
    res = D.compute_diff(st)
    assert any(e.kind == "flip" for e in res.events)


def test_streak_renders_ordinal():
    st = _state({"sp500": [10, 11, 12, 13, 14]})  # 4th straight higher
    res = D.compute_diff(st)
    assert "4th straight session" in res.line


def test_line_caps_at_three_events():
    # Many metrics each set a new high simultaneously.
    rising = {k: [10 + i for i in range(5)] + [99.0] for k in METRIC_KEYS}
    st = _state(rising)
    res = D.compute_diff(st)
    assert res.line.count(";") <= 2  # at most 3 clauses => <=2 separators
