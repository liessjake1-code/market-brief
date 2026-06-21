from __future__ import annotations
from marketbrief.core.models import SectionVM
from marketbrief.sections._format import SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration


class WhatToWatchSection:
    id = "what_to_watch_today"
    order = 11

    def build(self, ctx) -> SectionVM | None:
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=quiet, lead=lead, why_lines=[] if quiet else deep)

    def is_quiet(self, ctx) -> bool:
        why = ctx.narration.get(self.id)
        return why is None or why.degraded or not why.text
