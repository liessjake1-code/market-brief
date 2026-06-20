from __future__ import annotations
import math
from marketbrief.core.models import Field, HealthReport

CORE_FIELDS: tuple[str, ...] = ("sp500", "nasdaq", "dow", "russell", "ust10y", "wti", "dxy")


def _is_numeric(value: float | None) -> bool:
    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(f)


def assess(
    fields: dict[str, Field],
    *,
    degraded_stale_threshold: int,
    hard_floor_missing_threshold: int,
    model_failed: bool = False,
) -> HealthReport:
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
        missing_core=missing_core,
        stale_core=stale_core,
        degraded=degraded,
        hard_floor_tripped=hard_floor_tripped,
    )
