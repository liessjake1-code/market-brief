from __future__ import annotations
from pydantic import BaseModel, Field as PField
from marketbrief.core.enums import SourceHealth, Verdict


class Field(BaseModel):
    metric: str
    value: float | None
    source: str
    stale: bool = False
    as_of: str | None = None
    note: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.value is None or self.source == "missing"

    @property
    def is_usable(self) -> bool:
        return (not self.is_missing) and (not self.stale)


class SourceResult(BaseModel):
    name: str
    fields: dict[str, Field] = PField(default_factory=dict)
    health: SourceHealth = SourceHealth.OK
    error: str | None = None


class ComputedNumbers(BaseModel):
    values: dict[str, float] = PField(default_factory=dict)
    diff_lines: list[str] = PField(default_factory=list)


class Cause(BaseModel):
    claim: str
    cause_source_id: str | None = None
    verdict: Verdict = Verdict.PASS


class NarratedWhy(BaseModel):
    section_id: str
    text: str
    causes: list[Cause] = PField(default_factory=list)
    degraded: bool = False


class SectionVM(BaseModel):
    id: str
    title: str
    order: int
    body: str
    quiet: bool = False


class HealthReport(BaseModel):
    missing_core: list[str] = PField(default_factory=list)
    stale_core: list[str] = PField(default_factory=list)
    degraded: bool = False
    hard_floor_tripped: bool = False


class Article(BaseModel):
    source_id: str
    title: str
    summary: str = ""
    url: str = ""


class NewsResult(BaseModel):
    name: str
    articles: list[Article] = PField(default_factory=list)
    health: SourceHealth = SourceHealth.OK
    error: str | None = None
