from __future__ import annotations
from typing import Protocol, TYPE_CHECKING, runtime_checkable
from marketbrief.core.models import SourceResult, SectionVM, Cause
from marketbrief.core.enums import Verdict

if TYPE_CHECKING:
    from marketbrief.core.context import BriefContext


@runtime_checkable
class DataSource(Protocol):
    name: str
    def fetch(self, ctx: "BriefContext") -> SourceResult: ...


@runtime_checkable
class Section(Protocol):
    id: str
    order: int
    def build(self, ctx: "BriefContext") -> SectionVM | None: ...
    def is_quiet(self, ctx: "BriefContext") -> bool: ...


@runtime_checkable
class Validator(Protocol):
    def judge(self, cause: Cause, ctx: "BriefContext") -> Verdict: ...
