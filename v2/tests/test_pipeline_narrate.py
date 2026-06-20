from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Article
from marketbrief.core.pipeline import run_pipeline


class FakeClient:
    """Sonnet narration call returns sections; Haiku entailment returns a verdict.
    Distinguished by the presence of 'sections' in the returned shape."""
    def parse(self, *, model, **kw):
        if "haiku" in model:
            return {"verdict": "supports"}
        return {"sections": [{
            "section_id": "commodities",
            "prose": "Oil rose on OPEC supply cut.",
            "cause": "OPEC", "cause_source_id": "cnbc-1", "confidence": "high",
        }]}


def _ctx():
    return BriefContext(
        run_date=date(2026, 6, 22), mode=RunMode.NO_SEND, config=Config(),
        articles=[Article(source_id="cnbc-1", title="Oil jumps on OPEC cut",
                          summary="opec supply")],
    )


def test_pipeline_narrates_and_validates_with_fake_client():
    ctx = run_pipeline(_ctx(), sources=[], sections=[], news_source=_NoNews(),
                       narration_client=FakeClient())
    why = ctx.narration["commodities"]
    assert why.text == "Oil rose on OPEC supply cut."
    assert why.degraded is False
    assert why.causes[0].verdict == Verdict.PASS


class _NoNews:
    def fetch_news(self, ctx):
        return None
