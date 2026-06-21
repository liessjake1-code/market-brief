"""Tests for the pure Movers compute: closes -> ranked winners/losers board."""
from marketbrief.core.enums import Direction
from marketbrief.compute.movers import compute_movers, _pct_return


def test_pct_return_basic():
    # 100 -> 110 over the lookback is +10%.
    assert _pct_return([100.0, 105.0, 110.0], 2) == 10.0
    # lookback longer than available -> None (not enough history).
    assert _pct_return([100.0, 110.0], 5) is None
    # zero base -> None (no division).
    assert _pct_return([0.0, 5.0], 1) is None


def test_day_winners_and_losers_ranked():
    # Three names with distinct 1-day moves; ensure ranking + direction.
    closes = {
        "WIN": [100.0, 105.0],   # +5% day
        "MID": [100.0, 100.0],   # flat
        "LOSE": [100.0, 96.0],   # -4% day
    }
    board = compute_movers(closes)
    day = next(p for p in board.periods if p.label == "Day")
    assert day.winners[0].ticker == "WIN"
    assert day.winners[0].direction == Direction.UP
    assert day.winners[0].value_str == "+5.0%"
    assert day.losers[0].ticker == "LOSE"
    assert day.losers[0].direction == Direction.DOWN
    assert day.losers[0].value_str == "-4.0%"


def test_top_three_slice_only():
    # Five winners; only the top 3 by move survive in the winners list.
    closes = {f"W{i}": [100.0, 100.0 + i] for i in range(1, 6)}  # +1%..+5%
    board = compute_movers(closes)
    day = next(p for p in board.periods if p.label == "Day")
    assert [m.ticker for m in day.winners] == ["W5", "W4", "W3"]
    assert len(day.winners) == 3


def test_week_and_month_windows_use_correct_lookback():
    # "BIG" is flat over the last session but up strongly across the month window;
    # it must lead Month and NOT appear among Day winners.
    series = [100.0] + [130.0] * 21  # 22 closes: jumped a month ago, flat since
    closes = {"BIG": series, "FLAT": [100.0] * len(series)}
    board = compute_movers(closes)
    month = next(p for p in board.periods if p.label == "Month")
    day = next(p for p in board.periods if p.label == "Day")
    assert month.winners[0].ticker == "BIG"
    assert month.winners[0].value_str == "+30.0%"   # 100 -> 130 over 21 sessions
    assert [m.ticker for m in day.winners] == []     # flat on the day


def test_month_window_boundary_off_by_one():
    # lookback=21 needs index closes[-22], i.e. at least 22 closes.
    exactly_22 = [100.0] * 21 + [110.0]   # len 22 -> appears in Month
    only_21 = [100.0] * 20 + [110.0]      # len 21 -> len <= lookback -> excluded
    board = compute_movers({"IN": exactly_22, "OUT": only_21})
    month = next(p for p in board.periods if p.label == "Month")
    names = [m.ticker for m in month.winners + month.losers]
    assert "IN" in names
    assert "OUT" not in names


def test_thin_history_name_excluded_not_fabricated():
    # A name with a single close cannot produce any window return -> never appears.
    closes = {"THIN": [100.0], "OK": [100.0, 110.0]}
    board = compute_movers(closes)
    day = next(p for p in board.periods if p.label == "Day")
    tickers = [m.ticker for m in day.winners + day.losers]
    assert "THIN" not in tickers
    assert "OK" in tickers


def test_empty_universe_yields_board_with_no_rows():
    board = compute_movers({})
    assert board.has_rows is False


def test_all_flat_universe_has_no_directional_movers():
    # Everything flat: no winners or losers worth showing.
    closes = {f"T{i}": [100.0, 100.0] for i in range(5)}
    board = compute_movers(closes)
    day = next(p for p in board.periods if p.label == "Day")
    assert day.winners == [] and day.losers == []
