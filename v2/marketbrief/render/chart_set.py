"""Build the default-on ChartRefs + CID->png map for a brief run.

Honors config.charts toggles. `_safe` wraps each build call so a chart
never blocks the brief (spec §7.5). Charts requiring rolling history (rates
trend, commodities trend, sparklines) are wired but no-op-skip when history
is unavailable. No chart ever fabricates data (spec §1, §6).
"""
from __future__ import annotations

import logging

from marketbrief.core.enums import ChartKind
from marketbrief.core.models import ChartRef
from marketbrief.render import charts as C


def _safe(fn):
    """Run fn(); return None on any exception so charts never block the brief."""
    try:
        return fn()
    except Exception as exc:
        logging.warning("chart build skipped: %s", exc)
        return None  # a chart never blocks the brief (spec §7.5)


def build_charts(ctx) -> tuple[dict[str, bytes], dict[str, list[ChartRef]]]:
    """Return (png_by_cid, refs_by_section_id) honoring config.charts toggles.

    Each section_id key maps to a list of ChartRef objects for that section.
    png_by_cid maps every referenced cid to its raw PNG bytes.
    Charts are skipped cleanly when their required data is not yet available.
    """
    cfg = ctx.config.charts
    png_by_cid: dict[str, bytes] = {}
    refs: dict[str, list[ChartRef]] = {}

    def add(section_id: str, chart, kind: ChartKind) -> None:
        if chart is None:
            return
        png_by_cid[chart.cid] = chart.png
        refs.setdefault(section_id, []).append(
            ChartRef(cid=chart.cid, alt=chart.title, kind=kind)
        )

    if cfg.equities:
        # Same-day per-index % changes are not yet available (compute deferred).
        # Pass changes={} and skip cleanly — no fabrication (spec §1).
        changes: dict[str, float] = {}
        add(
            "us_equities",
            _safe(lambda: C.index_change_bar(changes) if changes else None),
            ChartKind.BAR,
        )

    # Rates trend (default-on) — needs rolling 10-year history; deferred.
    # Wire point is here; skipped cleanly until history sub-project supplies series.
    if cfg.rates:
        add(
            "rates",
            _safe(lambda: C.ten_year_trend(ten_year_history=[])),
            ChartKind.LINE,
        )

    # Commodities trend (default-on) — needs rolling WTI/gold/copper history; deferred.
    if cfg.commodities:
        add(
            "commodities",
            _safe(lambda: C.commodities_normalized(histories={})),
            ChartKind.LINE,
        )

    # Sparklines auto-on when watchlist is non-empty; deferred until history available.
    if ctx.config.watchlist:
        # No sparkline data yet — skip cleanly.
        pass

    return png_by_cid, refs
