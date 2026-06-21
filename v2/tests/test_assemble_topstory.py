"""Tests for marketbrief.assemble.topstory (Top Story float + mechanical suppression)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.core.models import ComputedNumbers, SectionVM, WhyLine
from marketbrief.assemble.topstory import order_sections, is_mechanical_date, FALLBACK_ORDER

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent  # v2/tests -> v2 -> repo root
_MECHANICAL_MOVES_PATH = str(_REPO_ROOT / "data" / "mechanical_moves.yaml")


def _sec(sid: str, order: int) -> SectionVM:
    return SectionVM(id=sid, title=sid, order=order, lead=WhyLine(text="x", hedged=True))


def _ctx(values: dict | None = None, run_date: date = date(2026, 6, 23)) -> BriefContext:
    return BriefContext(
        run_date=run_date,
        mode=RunMode.NO_SEND,
        config=Config(),
        numbers=ComputedNumbers(values=values or {}),
    )


_FALLBACK = list(FALLBACK_ORDER)


# ---------------------------------------------------------------------------
# Group 1: prescribed tests from the brief (run_date=2026-06-23, not mechanical)
# ---------------------------------------------------------------------------

def test_fallback_order_when_no_trigger():
    secs = [_sec(s, i + 1) for i, s in enumerate(_FALLBACK)]
    out = order_sections(_ctx(), secs)
    assert [s.id for s in out] == _FALLBACK
    assert all(not s.is_promoted for s in out)


def test_large_rate_move_promotes_rates():
    secs = [_sec(s, i + 1) for i, s in enumerate(_FALLBACK)]
    # 10-year up >8bps drives promotion of rates_and_dollar (spec §5.2)
    out = order_sections(_ctx({"ust10y_change_bps": 12.0}), secs)
    assert out[0].id == "rates_and_dollar" and out[0].is_promoted is True


# ---------------------------------------------------------------------------
# Group 2: real data file tests for is_mechanical_date
#
# Dates verified from data/mechanical_moves.yaml:
#   - 2026-06-26 is present under russell_reconstitution (fourth Friday in June)
#   - 2026-06-23 is NOT present in any section
# ---------------------------------------------------------------------------

def test_is_mechanical_date_true_for_real_date():
    """2026-06-26 appears under russell_reconstitution in the real yaml file."""
    result = is_mechanical_date(date(2026, 6, 26), path=_MECHANICAL_MOVES_PATH)
    assert result is True


def test_is_mechanical_date_false_for_non_mechanical_date():
    """2026-06-23 is a normal Monday; it does not appear in mechanical_moves.yaml."""
    result = is_mechanical_date(date(2026, 6, 23), path=_MECHANICAL_MOVES_PATH)
    assert result is False


# ---------------------------------------------------------------------------
# Group 3: mechanical date suppresses promotion
#
# Uses 2026-06-26 (Russell reconstitution) as the mechanical date.
# Even with a large rate move trigger, promotion must be suppressed.
# ---------------------------------------------------------------------------

def test_mechanical_date_suppresses_promotion():
    """On a mechanical date a qualifying move does NOT promote any section."""
    mechanical_run_date = date(2026, 6, 26)
    secs = [_sec(s, i + 1) for i, s in enumerate(_FALLBACK)]
    # ust10y_change_bps=12.0 would normally promote rates_and_dollar
    ctx = _ctx(values={"ust10y_change_bps": 12.0}, run_date=mechanical_run_date)
    # Override is_mechanical_date to use the real file via explicit path embedded in ctx
    # Since order_sections calls is_mechanical_date with the default path, and the default
    # "data/mechanical_moves.yaml" resolves from repo root (where brief.py runs), we need
    # to ensure the test exercises the real suppression logic.
    # We pass the absolute path via a monkeypatch to simulate the mechanical date detection.
    import marketbrief.assemble.topstory as ts
    original = ts.is_mechanical_date

    def patched(run_date_arg, path="data/mechanical_moves.yaml"):
        return original(run_date_arg, path=_MECHANICAL_MOVES_PATH)

    ts.is_mechanical_date = patched
    try:
        out = order_sections(ctx, secs)
    finally:
        ts.is_mechanical_date = original

    assert [s.id for s in out] == _FALLBACK, "Order must be fallback order on mechanical date"
    assert all(not s.is_promoted for s in out), "No section should be promoted on a mechanical date"


# ---------------------------------------------------------------------------
# Group 4: default path (no path arg) resolves via module-level constant
# ---------------------------------------------------------------------------

def test_is_mechanical_date_no_path_arg_uses_real_yaml():
    """is_mechanical_date with no path arg must resolve via _DEFAULT_MECH_PATH
    (anchored to repo root) and correctly identify 2026-06-26 (Russell reconstitution)."""
    result = is_mechanical_date(date(2026, 6, 26))
    assert result is True, (
        "is_mechanical_date(date(2026,6,26)) should return True using the default path "
        "(_DEFAULT_MECH_PATH anchored to repo root, not cwd)"
    )
