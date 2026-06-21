from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field as PField
from marketbrief.core.enums import SourceHealth, Verdict, Direction, ChartKind


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


class FigureCell(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_label: str
    value_str: str
    change_str: str
    direction: Direction
    source_url: str | None = None
    stale: bool = False
    mechanical: bool = False


class StatRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    label: str
    cells: list[FigureCell] = PField(default_factory=list)


class WhyLine(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    source_url: str | None = None
    source_label: str | None = None
    hedged: bool = False


class ChartRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    cid: str
    alt: str
    kind: ChartKind


class GlanceRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    category: str
    latest: str
    why_brief: str = ""  # retired from At a Glance; kept for back-compat, always empty
    is_live: bool = False


class MoverRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    ticker: str
    favicon_url: str | None
    value_str: str
    direction: Direction
    why: str
    source_url: str | None = None


class MoverPeriod(BaseModel):
    """Top winners and losers over one trailing window (day / week / month).

    `label` is the human window name shown in the template ("Day"). `winners` and
    `losers` are already ranked and sliced (top N) by the assemble layer; the
    template only iterates. Either list may be empty when data is thin.
    """

    model_config = ConfigDict(frozen=True)
    label: str
    winners: list[MoverRow] = PField(default_factory=list)
    losers: list[MoverRow] = PField(default_factory=list)


class MoverBoard(BaseModel):
    """The Movers board: top winners/losers across day, week, and month windows.

    Defaults empty so a quiet movers section (per-stock universe deferred, spec §7)
    carries no board. The template renders a period block only when it has rows, so
    an empty board renders nothing — no fabricated names.
    """

    model_config = ConfigDict(frozen=True)
    periods: list[MoverPeriod] = PField(default_factory=list)

    @property
    def has_rows(self) -> bool:
        return any(p.winners or p.losers for p in self.periods)


class SparkRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    ticker: str
    cid: str


class LiveSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    as_of_label: str
    rows: list[FigureCell] = PField(default_factory=list)
    is_premarket: bool = True


class SectionVM(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    order: int
    quiet: bool = False
    lead: WhyLine
    stat_rows: list[StatRow] = PField(default_factory=list)
    why_lines: list[WhyLine] = PField(default_factory=list)
    charts: list[ChartRef] = PField(default_factory=list)
    movers: list[MoverRow] = PField(default_factory=list)
    mover_board: MoverBoard | None = None
    sparklines: list[SparkRef] = PField(default_factory=list)
    is_promoted: bool = False


class BriefView(BaseModel):
    model_config = ConfigDict(frozen=True)
    diff_line: str
    glance_rows: list[GlanceRow] = PField(default_factory=list)
    sections: list[SectionVM] = PField(default_factory=list)
    live: LiveSnapshot | None = None
    degraded: bool = False
    banner_text: str | None = None
    date_label: str = ""
    png_by_cid: dict[str, bytes] = PField(default_factory=dict)


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
