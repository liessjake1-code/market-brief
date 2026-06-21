from __future__ import annotations
from marketbrief.core.models import WhyLine
from marketbrief.sections._format import quiet_lead
from marketbrief.render.source_links import source_url  # noqa: F401  (kept for parity)


def why_lines_from_narration(section_id: str, ctx) -> tuple[WhyLine, list[WhyLine]]:
    """Bridge NarratedWhy -> (lead WhyLine, deep WhyLines).

    Falls back to the honest quiet line when narration is absent, degraded, or
    has no usable causes. An unsourced cause is always hedged (spec §2 grounding).
    """
    why = ctx.narration.get(section_id)
    if why is None or why.degraded or not why.text:
        return quiet_lead(section_id), []
    has_source = any(c.cause_source_id for c in why.causes)
    lead = WhyLine(text=why.text, source_url=None, hedged=not has_source)
    deep: list[WhyLine] = []
    for c in why.causes:
        deep.append(WhyLine(text=c.claim, source_url=None,
                            hedged=c.cause_source_id is None))
    return lead, deep
