from datetime import date
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth
from marketbrief.core.models import SourceResult, Field
from marketbrief.sources.rss_source import RssSource


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


class _YF:
    name = "yfinance"
    def fetch(self, ctx):
        return SourceResult(name="yfinance", fields={
            k: Field(metric=k, value=100.0, source="yfinance")
            for k in ("sp500", "nasdaq", "dow", "russell", "wti", "dxy")
        }, health=SourceHealth.OK)


class _Fred:
    name = "fred"
    def fetch(self, ctx):
        return SourceResult(name="fred", fields={
            "ust10y": Field(metric="ust10y", value=4.2, source="fred", as_of="2026-06-19")
        }, health=SourceHealth.OK)


def _news():
    return RssSource(feed_fetcher=lambda u: "", feeds=())  # yields no articles, never network


def test_pipeline_resolves_fields_from_sources():
    out = run_pipeline(_ctx(), sources=[_YF(), _Fred()], sections=[], news_source=_news())
    assert out.resolved_fields["sp500"].value == 100.0
    assert out.resolved_fields["ust10y"].source == "fred"
    assert out.health.hard_floor_tripped is False


def test_yfinance_down_resolves_core_from_stooq():
    class _Stooq:
        name = "stooq"
        def fetch(self, ctx):
            return SourceResult(name="stooq", fields={
                k: Field(metric=k, value=50.0, source="stooq")
                for k in ("sp500", "nasdaq", "dow", "russell", "wti", "dxy")
            }, health=SourceHealth.OK)
    class _BoomYF:
        name = "yfinance"
        def fetch(self, ctx):
            raise RuntimeError("Yahoo blocked")
    out = run_pipeline(_ctx(), sources=[_BoomYF(), _Stooq(), _Fred()], sections=[], news_source=_news())
    assert out.resolved_fields["sp500"].source == "stooq"
    assert out.facts["yfinance"].health is SourceHealth.FAILED
    assert out.health.hard_floor_tripped is False  # survived the block


def test_news_attached_to_context():
    news = RssSource(feed_fetcher=lambda u: (
        '<rss><channel><item><title>Hi</title><link>http://x</link></item></channel></rss>'
    ), feeds=("http://cnbc",))
    out = run_pipeline(_ctx(), sources=[_YF()], sections=[], news_source=news)
    assert any(a.title == "Hi" for a in out.articles)
