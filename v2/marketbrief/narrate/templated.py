"""Deterministic fallback 'why' lines (spec ss5.6, ss7.5 degrade path).

When the model is offline or fails, the brief still ships with flat templated lines
built from numbers and direction alone. No causes, no model. Always degraded=True."""
from __future__ import annotations
from marketbrief.core.models import ComputedNumbers, NarratedWhy
from marketbrief.match.keywords import SECTION_KEYWORDS


def templated_why(section_id: str, numbers: ComputedNumbers) -> NarratedWhy:
    return NarratedWhy(
        section_id=section_id,
        text="No model commentary available; see the figures above.",
        causes=[],
        degraded=True,
    )


def templated_all(numbers: ComputedNumbers) -> dict[str, NarratedWhy]:
    return {sid: templated_why(sid, numbers) for sid in SECTION_KEYWORDS}
