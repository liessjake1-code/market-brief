from __future__ import annotations
from datetime import datetime
from marketbrief.core.models import LiveSnapshot, FigureCell

_OPEN_MINUTES = 8 * 60 + 30  # 8:30 AM CT cash open (spec §3.1)


def build_live_snapshot(pull_time_ct: datetime, rows: list[FigureCell]) -> LiveSnapshot:
    minutes = pull_time_ct.hour * 60 + pull_time_ct.minute
    is_pre = minutes < _OPEN_MINUTES
    word = "Pre-market" if is_pre else "Early session"
    label = f"{word} as of {pull_time_ct:%H:%M} CT"
    return LiveSnapshot(as_of_label=label, rows=rows, is_premarket=is_pre)
