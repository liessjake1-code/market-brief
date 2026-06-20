"""Same-day compute stage (PURE, no I/O, no model).

Builds the ComputedNumbers input set the number-validator checks against and the
narrator may cite. Computes ONLY figures available from today's resolved fields:
each usable field's value, plus same-day spreads (2s10s). Rolling-history figures
(5/20-day high/low, streaks, weekly sums, z-scores, 'yesterday') are deliberately
NOT computed here; they belong to the later compute sub-project.
"""
from __future__ import annotations

from marketbrief.core.config import Config
from marketbrief.core.models import ComputedNumbers, Field

TEN_YEAR = "ust10y"
TWO_YEAR = "ust2y"


def derive_numbers(
    resolved_fields: dict[str, Field], config: Config
) -> ComputedNumbers:
    """Derive same-day numbers from resolved fields.

    Args:
        resolved_fields: Mapping of metric name to Field, as produced by the
            resolver. Only usable (non-missing, non-stale) fields contribute.
        config: Application config (reserved for future use).

    Returns:
        ComputedNumbers with each usable field value and any same-day spreads.
    """
    values: dict[str, float] = {}

    for metric, field in resolved_fields.items():
        if field.is_usable and field.value is not None:
            values[metric] = field.value

    ten = resolved_fields.get(TEN_YEAR)
    two = resolved_fields.get(TWO_YEAR)
    if (
        ten is not None
        and two is not None
        and ten.is_usable
        and two.is_usable
        and ten.value is not None
        and two.value is not None
    ):
        values["spread_2s10s"] = ten.value - two.value

    return ComputedNumbers(values=values, diff_lines=[])
