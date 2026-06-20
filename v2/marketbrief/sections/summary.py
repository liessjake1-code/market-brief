from __future__ import annotations
from marketbrief.core.models import SectionVM


class SummarySection:
    id = "summary"
    order = 0

    def build(self, ctx) -> SectionVM | None:
        n = len(ctx.facts)
        return SectionVM(
            id=self.id,
            title="At a Glance",
            order=self.order,
            body=f"Brief assembled from {n} source(s).",
            quiet=self.is_quiet(ctx),
        )

    def is_quiet(self, ctx) -> bool:
        return False
