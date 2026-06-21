from __future__ import annotations
from marketbrief.sections._format import METRIC_LABELS

NO_CHANGE = "Markets little changed overnight."
_PCT_THRESHOLD = 0.5  # report a settled index move in the diff line at >= 0.5%
_DIFF_METRICS = ("sp500", "nasdaq", "dow", "russell")


def build_diff_line(ctx) -> str:
    prev_fields = (ctx.prev_state or {}).get("fields", {})
    best_label, best_pct = None, 0.0
    for metric in _DIFF_METRICS:
        field = ctx.resolved_fields.get(metric)
        if field is None or field.stale or field.value is None:
            continue  # stale fields are excluded from the diff line (spec §7.5)
        prev = prev_fields.get(metric)
        if not prev:
            continue
        pct = (field.value - prev) / prev * 100.0
        if abs(pct) >= _PCT_THRESHOLD and abs(pct) > abs(best_pct):
            best_label, best_pct = METRIC_LABELS.get(metric, metric), pct
    if best_label is None:
        return NO_CHANGE
    return f"{best_label} {best_pct:+.1f}% since yesterday's close."
