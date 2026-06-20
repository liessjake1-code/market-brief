from datetime import date
from marketbrief.narrate.chain import TagOnlyCauseCheck, run_chain
from marketbrief.core.models import Cause
from marketbrief.core.enums import Verdict, RunMode
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_tag_only_strips_uncited_causal_claim():
    cause = Cause(claim="Stocks fell because of weak data", cause_source_id=None)
    out = run_chain(cause, _ctx(), [TagOnlyCauseCheck()])
    assert out.verdict == Verdict.STRIP


def test_tag_only_passes_cited_causal_claim():
    cause = Cause(claim="Stocks fell because of weak data", cause_source_id="art-1")
    out = run_chain(cause, _ctx(), [TagOnlyCauseCheck()])
    assert out.verdict == Verdict.PASS


def test_strongest_verdict_wins():
    class Hedger:
        def judge(self, cause, ctx): return Verdict.HEDGE
    class Stripper:
        def judge(self, cause, ctx): return Verdict.STRIP
    cause = Cause(claim="no causal verb here", cause_source_id="art-1")
    out = run_chain(cause, _ctx(), [Hedger(), Stripper()])
    assert out.verdict == Verdict.STRIP


def test_throwing_validator_fails_closed_to_strip():
    class Boom:
        def judge(self, cause, ctx): raise RuntimeError("bad")
    cause = Cause(claim="anything", cause_source_id="art-1")
    out = run_chain(cause, _ctx(), [Boom()])
    assert out.verdict == Verdict.STRIP
