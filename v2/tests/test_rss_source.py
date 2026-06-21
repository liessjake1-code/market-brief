from datetime import date
from marketbrief.sources.rss_source import RssSource, parse_feed
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Stocks rise on data</title><description>Markets gained.</description><link>http://x/1</link></item>
<item><title>Fed holds rates</title><description>No change.</description><link>http://x/2</link></item>
</channel></rss>"""


def test_parse_feed_builds_articles_with_source_ids():
    arts = parse_feed(_RSS, prefix="cnbc")
    assert arts[0].source_id == "cnbc-0"
    assert arts[0].title == "Stocks rise on data"
    assert arts[1].source_id == "cnbc-1"


def test_fetch_news_aggregates_feeds():
    src = RssSource(feed_fetcher=lambda url: _RSS, feeds=("http://cnbc",))
    nr = src.fetch_news(_ctx())
    assert len(nr.articles) == 2
    assert nr.health is SourceHealth.OK


def test_single_feed_failure_is_skipped():
    def fetcher(url):
        if "bad" in url:
            raise RuntimeError("feed down")
        return _RSS
    src = RssSource(feed_fetcher=fetcher, feeds=("http://bad", "http://cnbc"))
    nr = src.fetch_news(_ctx())
    assert len(nr.articles) == 2  # only the good feed


def test_total_failure_returns_empty_never_raises():
    src = RssSource(feed_fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("x")), feeds=("http://a",))
    nr = src.fetch_news(_ctx())
    assert nr.articles == []
    assert nr.health is SourceHealth.OK  # news never blocks


def test_offline_returns_sample_articles(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    nr = RssSource().fetch_news(_ctx())
    assert len(nr.articles) >= 1
