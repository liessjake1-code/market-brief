from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Article, NewsResult
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
    ctx = run_pipeline(_ctx(), sources=[], sections=[], news_source=_SeedNews(),
                       narration_client=FakeClient())
    why = ctx.narration["commodities"]
    assert why.text == "Oil rose on OPEC supply cut."
    assert why.degraded is False
    assert why.causes[0].verdict == Verdict.PASS


class ContradictsClient:
    """Sonnet narration call returns sections; Haiku entailment returns 'contradicts'."""
    def parse(self, *, model, **kw):
        if "haiku" in model:
            return {"verdict": "contradicts"}
        return {"sections": [{
            "section_id": "commodities",
            "prose": "Oil rose on an OPEC supply cut.",
            "cause": "OPEC", "cause_source_id": "cnbc-1", "confidence": "high",
        }]}


class _SeedNews:
    """Returns the seeded cnbc-1 article so EntailmentCheck can find it."""
    def fetch_news(self, ctx):
        return NewsResult(name="seed", articles=list(ctx.articles))


def test_contradicts_verdict_degrades_narrated_section():
    ctx = run_pipeline(_ctx(), sources=[], sections=[], news_source=_SeedNews(),
                       narration_client=ContradictsClient())
    why = ctx.narration["commodities"]
    assert why.degraded is True
    assert why.causes[0].verdict == Verdict.STRIP
    assert why.text == "No model commentary available; see the figures above."
    assert why.text != "Oil rose on an OPEC supply cut."


class _NoNews:
    def fetch_news(self, ctx):
        return None
