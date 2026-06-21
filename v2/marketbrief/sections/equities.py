from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("sp500", "nasdaq", "dow", "russell")


class EquitiesSection:
    id = "us_equities"
    order = 1

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        stat_rows = [StatRow(label="Indices", cells=cells)] if cells else []
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order,
            quiet=quiet, lead=lead, stat_rows=stat_rows,
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
