from marketbrief.core.config import NarrateConfig
from marketbrief.core.models import ComputedNumbers, Article
from marketbrief.match.scorer import ScoredArticle
from marketbrief.narrate.narrator import narrate

CFG = NarrateConfig()
MATCHED = {"commodities": [ScoredArticle(
    Article(source_id="cnbc-1", title="Oil jumps", summary="opec"), 0.5)]}


class FakeClient:
    def __init__(self, payload=None, boom=False):
        self.payload = payload
        self.boom = boom

    def parse(self, **kw):
        if self.boom:
            raise RuntimeError("api down")
        return self.payload


def test_offline_client_none_returns_templated():
    out = narrate(ComputedNumbers(values={}), MATCHED, client=None, config=CFG)
    assert out["commodities"].degraded is True
    assert out["commodities"].causes == []


def test_successful_narration_tags_cause():
    payload = {"sections": [{
        "section_id": "commodities", "prose": "Oil rose on OPEC supply news.",
        "cause": "OPEC supply", "cause_source_id": "cnbc-1", "confidence": "high",
    }]}
    out = narrate(ComputedNumbers(values={"wti": 76.1}), MATCHED,
                  client=FakeClient(payload), config=CFG)
    w = out["commodities"]
    assert w.degraded is False
    assert w.text == "Oil rose on OPEC supply news."
    assert len(w.causes) == 1
    assert w.causes[0].cause_source_id == "cnbc-1"


def test_client_failure_falls_back_to_templated():
    out = narrate(ComputedNumbers(values={}), MATCHED,
                  client=FakeClient(boom=True), config=CFG)
    assert out["commodities"].degraded is True


def test_no_cause_yields_causeless_why():
    payload = {"sections": [{
        "section_id": "commodities", "prose": "No clear catalyst.",
        "cause": None, "cause_source_id": None, "confidence": "low",
    }]}
    out = narrate(ComputedNumbers(values={}), MATCHED,
                  client=FakeClient(payload), config=CFG)
    assert out["commodities"].causes == []
    assert out["commodities"].degraded is False
