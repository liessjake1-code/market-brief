from __future__ import annotations
from marketbrief.core.models import GlanceRow

# At-a-Glance categories in spec §4.1 order. "This morning" is the one live row.
_CATEGORIES = (
    ("Markets", False), ("Rates and dollar", False), ("Commodities", False),
    ("Crypto", False), ("Volatility", False), ("This morning", True),
    ("Today's events", False), ("Earnings", False), ("Washington", False),
    ("Bottom line", False),
)


# Separator between labeled figures in a glance row, e.g. "S&P 5,000 · Nasdaq 18,000".
_FIGURE_SEP = " · "  # middle dot


def build_glance_rows(ctx, sections) -> list[GlanceRow]:
    by_id = {s.id: s for s in sections}

    def latest_for(*ids: str) -> str:
        """Labeled figures only (no explanation): "S&P 5,000 · Nasdaq 18,000".

        Each number carries its metric label so the reader knows which is which;
        the causal "why" lives in the section, not here (At a Glance is numbers only).
        """
        for sid in ids:
            s = by_id.get(sid)
            if s and s.stat_rows and s.stat_rows[0].cells:
                return _FIGURE_SEP.join(
                    f"{c.metric_label} {c.value_str}" for c in s.stat_rows[0].cells
                )
        return "n/a"

    mapping = {
        "Markets": ("us_equities",),
        "Rates and dollar": ("rates_and_dollar",),
        "Commodities": ("commodities",),
        "Crypto": ("crypto",),
        "Volatility": ("volatility_breadth",),
        "Today's events": ("what_to_watch_today",),
        "Earnings": ("earnings_on_deck",),
        "Washington": ("washington",),
    }
    rows: list[GlanceRow] = []
    for category, is_live in _CATEGORIES:
        ids = mapping.get(category, ())
        rows.append(GlanceRow(
            category=category,
            latest="" if is_live or category == "Bottom line" else latest_for(*ids),
            why_brief="",  # At a Glance is numbers only; the "why" lives in each section.
            is_live=is_live,
        ))
    return rows
