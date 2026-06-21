from __future__ import annotations
from marketbrief.core.models import GlanceRow

# At-a-Glance categories in spec §4.1 order. "This morning" is the one live row.
_CATEGORIES = (
    ("Markets", False), ("Rates and dollar", False), ("Commodities", False),
    ("Crypto", False), ("Volatility", False), ("This morning", True),
    ("Today's events", False), ("Earnings", False), ("Washington", False),
    ("Bottom line", False),
)


def build_glance_rows(ctx, sections) -> list[GlanceRow]:
    by_id = {s.id: s for s in sections}

    def latest_for(*ids: str) -> str:
        for sid in ids:
            s = by_id.get(sid)
            if s and s.stat_rows and s.stat_rows[0].cells:
                return ", ".join(c.value_str for c in s.stat_rows[0].cells)
        return "n/a"

    def why_for(*ids: str) -> str:
        for sid in ids:
            s = by_id.get(sid)
            if s:
                return s.lead.text
        return ""

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
            why_brief=why_for(*ids) if ids else "",
            is_live=is_live,
        ))
    return rows
