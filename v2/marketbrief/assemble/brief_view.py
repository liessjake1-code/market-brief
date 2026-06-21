from __future__ import annotations
from marketbrief.core.models import BriefView, LiveSnapshot
from marketbrief.assemble.banner import banner_text


def build_brief_view(ctx, ordered_sections, glance_rows, diff_line,
                     live: LiveSnapshot | None) -> BriefView:
    text = banner_text(ctx.health)
    return BriefView(
        diff_line=diff_line, glance_rows=glance_rows, sections=ordered_sections,
        live=live, degraded=ctx.health.degraded, banner_text=text,
    )
