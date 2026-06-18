"""Loaders for the two static calendar files (spec §5 step 1, §7.7; roadmap §4).

These files are hand-authored and source-verified; they are USED as-is and never
regenerated (CLAUDE.md). This module only parses them into lookup structures the
Top Story engine queries by date.

  - tier_one_calendar.yaml -> which section a tier-one event promotes today
  - mechanical_moves.yaml   -> which metrics' moves are mechanical (suppress promote)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Optional

import yaml

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
TIER_ONE_FILE = "tier_one_calendar.yaml"
MECHANICAL_FILE = "mechanical_moves.yaml"

# Event categories carried in tier_one_calendar.yaml, in priority order. FOMC
# wins ties (a policy day outranks a data day for the Top Story slot).
TIER_ONE_CATEGORIES = ("fomc", "cpi", "nfp", "pce", "gdp")

# mechanical_moves.yaml "affected" tokens -> metric keys whose move is mechanical.
AFFECTED_TO_METRICS: dict[str, tuple[str, ...]] = {
    "us_equities": ("sp500", "nasdaq", "dow", "russell"),
    "volatility_breadth": ("vix",),
    "commodities": ("wti", "gold"),
    "rates_and_dollar": ("ust10y", "ust2y", "dxy"),
}


@dataclass(frozen=True)
class TierOneHit:
    category: str        # "fomc" | "cpi" | "nfp" | "pce" | "gdp"
    promotes: str        # section id, e.g. "washington" or "economic_data_scorecard"
    sep: bool = False     # FOMC SEP/dot-plot day


def _load_yaml(filename: str, data_dir: Optional[str] = None) -> dict:
    path = os.path.join(data_dir or DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{filename} did not parse to a mapping")
    return data


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def tier_one_for(day: date, *, data_dir: Optional[str] = None) -> Optional[TierOneHit]:
    """Return the tier-one hit for `day`, or None. FOMC outranks data releases.

    The promotes map comes from the file's meta.promotes_map so the data file
    stays the source of truth for the FOMC->washington / data->scorecard routing.
    """
    cal = _load_yaml(TIER_ONE_FILE, data_dir)
    promotes_map = (cal.get("meta", {}) or {}).get("promotes_map", {})
    for category in TIER_ONE_CATEGORIES:
        for entry in cal.get(category, []) or []:
            if _as_date(entry.get("date")) == day:
                return TierOneHit(
                    category=category,
                    promotes=promotes_map.get(category, "economic_data_scorecard"),
                    sep=bool(entry.get("sep", False)),
                )
    return None


def mechanical_metrics_for(day: date, *, data_dir: Optional[str] = None) -> set[str]:
    """Set of metric keys whose move is mechanical (suppress promotion) on `day`.

    Unions the `affected` lists of every mechanical entry matching the date,
    mapped from section tokens to metric keys.
    """
    cal = _load_yaml(MECHANICAL_FILE, data_dir)
    affected_metrics: set[str] = set()
    for key, entries in cal.items():
        if key == "meta" or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or "date" not in entry:
                continue
            if _as_date(entry["date"]) != day:
                continue
            for token in entry.get("affected", []) or []:
                affected_metrics.update(AFFECTED_TO_METRICS.get(token, ()))
    return affected_metrics
