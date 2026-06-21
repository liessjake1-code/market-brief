from __future__ import annotations
from marketbrief.core.models import HealthReport

_BANNER = ("Some sources returned limited data or could not be refreshed this morning. "
           "Read the figures with that in mind.")


def banner_text(health: HealthReport) -> str | None:
    return _BANNER if health.degraded else None
