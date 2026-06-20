from __future__ import annotations
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.health import CORE_FIELDS


class PlaceholderSource:
    name = "placeholder"

    def fetch(self, ctx) -> SourceResult:
        fields = {k: Field(metric=k, value=1.0, source="offline") for k in CORE_FIELDS}
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
