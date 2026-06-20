from __future__ import annotations
import re
from marketbrief.core.models import Cause
from marketbrief.core.enums import Verdict
from marketbrief.core.context import BriefContext
from marketbrief.core.protocols import Validator
from marketbrief.core.isolation import run_isolated

# Ported verbatim from engine/matcher.py
_CAUSAL_RE = re.compile(
    r"\b(because|due to|on (?:soft|strong|weak|robust|the)|amid|after|as|driven by|"
    r"thanks to|owing to|spurred by|fueled by|on the back of)\b",
    re.IGNORECASE,
)

_RANK = {Verdict.PASS: 0, Verdict.HEDGE: 1, Verdict.STRIP: 2}


class TagOnlyCauseCheck:
    """A causal verb requires a non-null cause_source_id (ported §5.6 cause check)."""

    def judge(self, cause: Cause, ctx: BriefContext) -> Verdict:
        has_causal = bool(_CAUSAL_RE.search(cause.claim))
        if has_causal and not cause.cause_source_id:
            return Verdict.STRIP
        return Verdict.PASS


def run_chain(cause: Cause, ctx: BriefContext, validators: list[Validator]) -> Cause:
    worst = Verdict.PASS
    for v in validators:
        verdict, err = run_isolated(
            f"validator:{type(v).__name__}", lambda v=v: v.judge(cause, ctx), Verdict.STRIP
        )
        if _RANK[verdict] > _RANK[worst]:
            worst = verdict
    return cause.model_copy(update={"verdict": worst})
