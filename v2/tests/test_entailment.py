from datetime import date
from marketbrief.core.config import Config, NarrateConfig
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Cause, Article
from marketbrief.narrate.entailment import EntailmentCheck

CFG = NarrateConfig()


def _ctx(articles):
    return BriefContext(run_date=date(2026, 6, 22), mode=RunMode.NO_SEND,
                        config=Config(), articles=articles)


class FakeClient:
    def __init__(self, verdict="supports", boom=False):
        self.verdict = verdict
        self.boom = boom

    def parse(self, **kw):
        if self.boom:
            raise RuntimeError("haiku down")
        return {"verdict": self.verdict}


ART = Article(source_id="cnbc-1", title="Oil jumps on OPEC cut", summary="opec")
CAUSE = Cause(claim="Oil rose on OPEC supply cut", cause_source_id="cnbc-1")


def test_supports_passes():
    ec = EntailmentCheck(FakeClient("supports"), CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.PASS


def test_weak_hedges():
    ec = EntailmentCheck(FakeClient("weak"), CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.HEDGE


def test_contradicts_strips():
    ec = EntailmentCheck(FakeClient("contradicts"), CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.STRIP


def test_no_client_passes():
    ec = EntailmentCheck(None, CFG)
    assert ec.judge(CAUSE, _ctx([ART])) == Verdict.PASS


def test_no_cause_source_id_passes():
    ec = EntailmentCheck(FakeClient("contradicts"), CFG)
    causeless = Cause(claim="markets were quiet", cause_source_id=None)
    assert ec.judge(causeless, _ctx([ART])) == Verdict.PASS


def test_missing_article_passes():
    ec = EntailmentCheck(FakeClient("contradicts"), CFG)
    orphan = Cause(claim="x", cause_source_id="nope-9")
    assert ec.judge(orphan, _ctx([ART])) == Verdict.PASS


def test_client_failure_raises_for_chain_to_strip():
    import pytest
    ec = EntailmentCheck(FakeClient(boom=True), CFG)
    with pytest.raises(RuntimeError):
        ec.judge(CAUSE, _ctx([ART]))
