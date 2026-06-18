"""Top Story rules engine (spec §5, §5.1, §7.7; roadmap §4).

Decides WHAT LEADS, deterministically, on settled finished-day data only. No
model. Priority order, stop at the first match:

  1. Tier-one calendar event today  -> promote its section (FOMC->washington,
     CPI/NFP/PCE/GDP->economic_data_scorecard). (spec §5 step 1)
  2. Large move in a core metric that clears its RAW trigger floor; among those
     that qualify, promote the largest STANDARDIZED (z-score) move. (spec §5
     step 2, §5.1)
  3. Quiet-tape floor: nothing clears -> fallback order, read "quiet tape". Never
     manufacture a Washington headline. (spec §5 step 3)

Mechanical-move guard (spec §5, §7.7): before step 2 promotes a move, if today
is a listed mechanical date for that metric, the move is ANNOTATED mechanical and
NOT promoted (no news story to ground a calendar artifact).

Settled data only: the engine reads the cached settled history, never a pre-market
tick (spec §5; roadmap §4.9).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from engine.calendars import mechanical_metrics_for, tier_one_for
from engine.metrics import is_yield
from engine.state import State

# Fixed fallback section order when no override fires (spec §4.2).
FALLBACK_ORDER: tuple[str, ...] = (
    "us_equities",
    "rates_and_dollar",
    "commodities",
    "washington",
    "movers",
    "economic_data_scorecard",
    "earnings_on_deck",
    "watchlist",
    "crypto",
    "volatility_breadth",
    "what_to_watch_today",
)

# Raw-trigger floors: a move must clear these to be ELIGIBLE at all (spec §5
# step 2). Units: bps for the 10-year, percent for the rest.
RAW_TRIGGERS: dict[str, float] = {
    "ust10y": 8.0,   # > 8 bps
    "wti": 3.0,      # > 3 %
    "sp500": 1.0,    # > 1 %
    "vix": 15.0,     # > 15 %
}

# Which section each triggering metric promotes (spec §5 step 2).
METRIC_PROMOTES: dict[str, str] = {
    "ust10y": "rates_and_dollar",
    "wti": "commodities",
    "sp500": "us_equities",
    "vix": "volatility_breadth",
}

ZSCORE_WINDOW = 20  # rolling 20-trading-day std of daily moves (spec §5.1)


@dataclass
class TopStoryDecision:
    section: str                     # the promoted Top Story section id
    reason: str                      # "tier_one" | "large_move" | "quiet_tape"
    detail: str                      # human-readable explanation
    order: list[str] = field(default_factory=list)   # full section order, Top Story first
    mechanical_notes: dict[str, str] = field(default_factory=dict)  # metric -> note
    tier_one_category: Optional[str] = None


# --------------------------------------------------------------------------- #
# Move math (settled history only)
# --------------------------------------------------------------------------- #
def _daily_moves(history: list[float], *, as_bps: bool) -> list[float]:
    """Session-over-session moves from settled closes.

    Percent change for prices; absolute level change scaled to bps for yields
    (a yield history is in percent, so a 0.08 move is 8 bps).
    """
    moves: list[float] = []
    for i in range(1, len(history)):
        prev, cur = history[i - 1], history[i]
        if as_bps:
            moves.append((cur - prev) * 100.0)  # 0.08 pct-pts -> 8 bps
        else:
            if prev == 0:
                moves.append(0.0)
            else:
                moves.append((cur - prev) / prev * 100.0)
    return moves


def latest_move(state: State, key: str) -> Optional[float]:
    """The most recent settled session move (bps for yields, percent otherwise)."""
    history = state.history(key)
    if len(history) < 2:
        return None
    return _daily_moves(history, as_bps=is_yield(key))[-1]


def zscore(state: State, key: str) -> Optional[float]:
    """Standardize the latest move against the rolling 20-day std of moves (§5.1).

    Returns None when history is too thin to compute a stable std. A single large
    move inflates the std (spec §5.1 caveat); the raw-trigger floor absorbs most
    of that, so the z-score only ranks already-eligible moves.
    """
    history = state.history(key)
    if len(history) < 3:
        return None
    moves = _daily_moves(history, as_bps=is_yield(key))
    window = moves[-(ZSCORE_WINDOW + 1):-1] if len(moves) > ZSCORE_WINDOW else moves[:-1]
    if len(window) < 2:
        return None
    sd = statistics.pstdev(window)
    if sd == 0:
        return None
    return moves[-1] / sd


# --------------------------------------------------------------------------- #
# The engine
# --------------------------------------------------------------------------- #
def _build_order(top: str) -> list[str]:
    """Pull `top` to the front; keep the rest in the fixed fallback order (§4.2)."""
    rest = [s for s in FALLBACK_ORDER if s != top]
    return [top] + rest


def decide(
    state: State,
    *,
    day: date,
    stale_keys: Optional[set[str]] = None,
    data_dir: Optional[str] = None,
) -> TopStoryDecision:
    stale_keys = stale_keys or set()

    # --- Step 1: tier-one calendar event today --------------------------- #
    hit = tier_one_for(day, data_dir=data_dir)
    if hit:
        detail = f"Tier-one event today ({hit.category.upper()}) promotes {hit.promotes}."
        return TopStoryDecision(
            section=hit.promotes,
            reason="tier_one",
            detail=detail,
            order=_build_order(hit.promotes),
            tier_one_category=hit.category,
        )

    # --- Mechanical-move guard set for today ----------------------------- #
    mechanical = mechanical_metrics_for(day, data_dir=data_dir)
    mechanical_notes: dict[str, str] = {}

    # --- Step 2: largest standardized qualifying move -------------------- #
    candidates: list[tuple[float, str, str]] = []  # (abs_z, metric, section)
    for key, floor in RAW_TRIGGERS.items():
        if key in stale_keys:
            continue  # stale fields never drive the engine (spec §7.5)
        move = latest_move(state, key)
        if move is None or abs(move) <= floor:
            continue
        if key in mechanical:
            # Report-but-suppress: annotate, do not promote (spec §7.7).
            mechanical_notes[key] = (
                f"{key} moved {move:+.1f} on a mechanical date; discounted, not promoted."
            )
            continue
        z = zscore(state, key)
        if z is None:
            continue
        candidates.append((abs(z), key, METRIC_PROMOTES[key]))

    if candidates:
        _, metric, section = max(candidates, key=lambda c: c[0])
        detail = f"Largest standardized move clears its trigger: {metric} promotes {section}."
        return TopStoryDecision(
            section=section,
            reason="large_move",
            detail=detail,
            order=_build_order(section),
            mechanical_notes=mechanical_notes,
        )

    # --- Step 3: quiet-tape floor ---------------------------------------- #
    return TopStoryDecision(
        section="us_equities",
        reason="quiet_tape",
        detail="No tier-one event and nothing cleared its trigger: quiet tape.",
        order=list(FALLBACK_ORDER),
        mechanical_notes=mechanical_notes,
    )
