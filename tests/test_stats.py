"""Section stat tables: session / week / month change, computed in Python (§1)."""
from __future__ import annotations

from engine import stats


def _series(n: int, start: float, step: float) -> list[float]:
    return [round(start + step * i, 4) for i in range(n)]


def test_price_changes_in_percent():
    # 22 sessions rising 1/unit: session +, week +, month +.
    hist = _series(22, 100.0, 1.0)  # 100 .. 121
    row = stats.stat_row("sp500", hist[-1], hist)
    assert row.session.direction == "up"
    assert row.session.text.endswith("%")
    assert row.week.direction == "up"
    assert row.month.direction == "up"
    assert row.level == "121"  # index display: no decimals


def test_yield_changes_in_bps():
    # 22 sessions, 10Y rising 0.01 (1 bp)/session -> week +5 bps, month +21 bps.
    hist = _series(22, 4.00, 0.01)
    row = stats.stat_row("ust10y", hist[-1], hist)
    assert "bps" in row.week.text
    assert row.week.text == "+5 bps"
    assert row.month.text == "+21 bps"
    assert row.level.endswith("%")


def test_thin_history_blanks_windows():
    # Only 3 closes: session computes, week/month blank.
    hist = [100.0, 101.0, 102.0]
    row = stats.stat_row("nasdaq", 102.0, hist)
    assert not row.session.is_blank
    assert row.week.is_blank
    assert row.month.is_blank


def test_flat_move_reads_flat():
    hist = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    row = stats.stat_row("dow", 100.0, hist)
    assert row.session.direction == "flat"
    assert row.session.text == "0.0%"


def test_negative_move_is_down():
    hist = _series(8, 100.0, -0.5)
    row = stats.stat_row("russell", hist[-1], hist)
    assert row.session.direction == "down"
    assert row.session.text.startswith("-")


def test_table_skips_fully_empty_metrics():
    table = stats.stat_table(
        ("sp500", "nasdaq", "dow"),
        values={"sp500": 6431.0, "nasdaq": None, "dow": 44000.0},
        histories={"sp500": _series(6, 6400, 5), "nasdaq": [], "dow": _series(6, 44000, 10)},
    )
    labels = [r.label for r in table.rows]
    assert "Nasdaq Composite" not in labels  # no value AND no history -> skipped
    assert len(table.rows) == 2


def test_table_keeps_value_with_thin_history():
    # A brand-new metric with a value but no history still appears (blank windows).
    table = stats.stat_table(
        ("cpi_yoy",),
        values={"cpi_yoy": 3.2},
        histories={"cpi_yoy": [3.2]},
    )
    assert len(table.rows) == 1
    assert table.rows[0].week.is_blank
    assert table.rows[0].level == "3.20%"


def test_empty_table():
    table = stats.stat_table(("sp500",), values={}, histories={})
    assert table.is_empty
