"""Field model + health check + degradation thresholds (spec §7.5; roadmap §5).

Every pulled metric becomes a Field carrying its value, the source it came from,
and whether it is stale (could not be freshly refreshed). Stale fields are
excluded from the diff line, the Top Story engine, and the explanation engine
(spec §7.5), so the rest of the pipeline asks each Field `is_usable`.

This module is pure (no network): the price/FRED layers produce Fields, and this
decides health, the degraded banner, and the hard floor against config
thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sources.symbols import CORE_FIELDS


class Source(str, Enum):
    YFINANCE = "yfinance"
    YFINANCE_BACKUP = "yfinance_backup"   # second price source (Stooq/Twelve Data)
    FRED = "fred"
    FRED_LAST_RESORT = "fred_last_resort"  # date-stamped oil last resort (spec §7.5)
    MISSING = "missing"


@dataclass
class Field:
    metric: str
    value: Optional[float]
    source: Source
    stale: bool = False
    as_of: Optional[str] = None      # date stamp when a value stands in for a fresher one
    note: Optional[str] = None        # e.g. "prior-session", "FRED lags several days"

    @property
    def is_missing(self) -> bool:
        return self.value is None or self.source is Source.MISSING

    @property
    def is_usable(self) -> bool:
        """Usable by diff / Top Story / narrative: present, numeric, not stale."""
        return (not self.is_missing) and (not self.stale)


@dataclass
class HealthReport:
    fields: dict[str, Field]
    missing_core: list[str]
    stale_core: list[str]
    degraded: bool
    hard_floor_tripped: bool

    @property
    def stale_keys(self) -> set[str]:
        return {k for k, f in self.fields.items() if f.stale or f.is_missing}


def _is_numeric(value: Optional[float]) -> bool:
    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return f == f  # NaN check (NaN != NaN)


def assess(
    fields: dict[str, Field],
    *,
    degraded_stale_threshold: int,
    hard_floor_missing_threshold: int,
    model_failed: bool = False,
) -> HealthReport:
    """Health check + degraded/hard-floor decision (spec §7.5).

    Core fields are the indices, 10-year, WTI, dollar (spec §7.5). The degraded
    banner trips when the model failed OR at least `degraded_stale_threshold`
    core fields are stale. The hard floor trips when MORE THAN
    `hard_floor_missing_threshold` core fields are missing.
    """
    missing_core: list[str] = []
    stale_core: list[str] = []
    for key in CORE_FIELDS:
        field = fields.get(key)
        if field is None or field.is_missing or not _is_numeric(field.value):
            missing_core.append(key)
        elif field.stale:
            stale_core.append(key)

    hard_floor_tripped = len(missing_core) > hard_floor_missing_threshold
    degraded = (
        model_failed
        or len(stale_core) >= degraded_stale_threshold
        or len(missing_core) >= degraded_stale_threshold
    )
    return HealthReport(
        fields=fields,
        missing_core=missing_core,
        stale_core=stale_core,
        degraded=degraded,
        hard_floor_tripped=hard_floor_tripped,
    )
