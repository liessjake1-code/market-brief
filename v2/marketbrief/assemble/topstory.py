"""Top Story float ordering and mechanical-move suppression.

Implements spec §4.2 (section order), §5.2 (standardized-move triggers),
and §7.7 (mechanical-move suppression of Top Story promotion).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from marketbrief.core.models import SectionVM

if TYPE_CHECKING:
    from marketbrief.core.context import BriefContext

# ---------------------------------------------------------------------------
# Default path for mechanical_moves.yaml — anchored to repo root so the
# module works regardless of cwd (spec §7.7 robustness requirement)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]   # assemble -> marketbrief -> v2 -> repo root
_DEFAULT_MECH_PATH = _REPO_ROOT / "data" / "mechanical_moves.yaml"

# ---------------------------------------------------------------------------
# Fixed fallback order (spec §4.2)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Standardized-move triggers (spec §5.2)
# Each entry: (computed_numbers_key, abs_threshold, section_id_to_promote)
# ---------------------------------------------------------------------------

_MOVE_TRIGGERS: tuple[tuple[str, float, str], ...] = (
    ("ust10y_change_bps", 8.0, "rates_and_dollar"),
    ("wti_change_pct", 3.0, "commodities"),
    ("sp500_change_pct", 1.0, "us_equities"),
)


def _as_date(value: object) -> date | None:
    """Coerce a YAML date value (datetime.date or ISO string) to date, or None."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def is_mechanical_date(run_date: date, path: str | Path | None = None) -> bool:
    """Return True if run_date is listed in the mechanical-moves calendar.

    Reads the YAML at path (defaults to _DEFAULT_MECH_PATH, anchored to repo
    root). Gracefully returns False if the file is missing or malformed.
    Handles the real schema where each top-level key (except "meta") maps to
    a list of dicts each carrying a "date" field.
    """
    p = Path(path) if path is not None else _DEFAULT_MECH_PATH
    if not p.exists():
        return False
    try:
        data = yaml.safe_load(p.read_text())
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False

    for key, value in data.items():
        if key == "meta":
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict) or "date" not in entry:
                continue
            entry_date = _as_date(entry["date"])
            if entry_date == run_date:
                return True

    return False


def _promoted_id(ctx: BriefContext) -> str | None:
    """Return the section id to promote, or None if no trigger fires or mechanical date."""
    if is_mechanical_date(ctx.run_date):
        return None  # mechanical move: report but do not promote (spec §7.7)

    values = ctx.numbers.values
    best_id: str | None = None
    best_excess = 0.0

    for name, trigger, section_id in _MOVE_TRIGGERS:
        v = values.get(name)
        if v is None:
            continue
        excess = abs(v) - trigger
        if excess > 0 and excess > best_excess:
            best_id = section_id
            best_excess = excess

    return best_id


def order_sections(ctx: BriefContext, sections: list[SectionVM]) -> list[SectionVM]:
    """Return sections in spec §4.2 fallback order, with promotion applied if triggered.

    If a standardized-move trigger fires and the run date is not a mechanical-move
    date, the winning section is pulled to the front with is_promoted=True.
    On a mechanical-move date, sections remain in fallback order (spec §7.7).
    """
    rank = {sid: i for i, sid in enumerate(FALLBACK_ORDER)}
    ordered = sorted(sections, key=lambda s: rank.get(s.id, 99))

    promoted = _promoted_id(ctx)
    if promoted is None:
        return ordered

    lead = [s for s in ordered if s.id == promoted]
    rest = [s for s in ordered if s.id != promoted]

    if not lead:
        return ordered

    promoted_vm = lead[0].model_copy(update={"is_promoted": True})
    return [promoted_vm, *rest]
