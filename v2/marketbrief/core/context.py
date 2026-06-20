from __future__ import annotations
from datetime import date
from pydantic import BaseModel, ConfigDict, Field as PField
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.models import (
    Field, Article, SourceResult, ComputedNumbers, Cause, NarratedWhy, SectionVM, HealthReport,
)


class BriefContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_date: date
    mode: RunMode
    config: Config
    prev_state: dict = PField(default_factory=dict)
    facts: dict[str, SourceResult] = PField(default_factory=dict)
    resolved_fields: dict[str, Field] = PField(default_factory=dict)
    articles: list[Article] = PField(default_factory=list)
    numbers: ComputedNumbers = PField(default_factory=ComputedNumbers)
    causes: list[Cause] = PField(default_factory=list)
    narration: dict[str, NarratedWhy] = PField(default_factory=dict)
    sections: list[SectionVM] = PField(default_factory=list)
    health: HealthReport = PField(default_factory=HealthReport)

    def with_updates(self, **kwargs) -> "BriefContext":
        return self.model_copy(update=kwargs)
