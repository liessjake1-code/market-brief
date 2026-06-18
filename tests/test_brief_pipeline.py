"""Phase 5 — brief.py orchestration (spec §7.5, §8.5; roadmap §5 gate).

Covers the hard-floor exit and the no-state-on-no-send invariant at the
orchestration level, using the offline seam so no network is touched.
"""

from __future__ import annotations

from datetime import date

import brief as B
from sources.quality import Field, Source


def _fields(missing: set[str] | None = None) -> dict[str, Field]:
    from engine.metrics import METRIC_KEYS
    missing = missing or set()
    out = {}
    for k in METRIC_KEYS:
        if k in missing:
            out[k] = Field(k, None, Source.MISSING)
        else:
            out[k] = Field(k, 100.0, Source.YFINANCE)
    return out


def test_hard_floor_exits_nonzero_no_send(monkeypatch, tmp_path, capsys):
    # 5 missing core fields > hard_floor_missing_threshold (4) -> trip.
    monkeypatch.setattr(
        B, "_gather_fields",
        lambda: _fields({"sp500", "nasdaq", "dow", "russell", "dxy"}),
    )
    rc = B.build_brief(send=False, today=date(2026, 6, 17))
    assert rc == B.EXIT_HARD_FLOOR
    out = capsys.readouterr().out
    assert "hard floor TRIPPED" in out


def test_clean_no_send_exits_zero_and_writes_no_state(monkeypatch):
    monkeypatch.setattr(B, "_gather_fields", lambda: _fields())
    rc = B.build_brief(send=False, today=date(2026, 6, 17))
    assert rc == B.EXIT_OK
