from __future__ import annotations
import html
import re
from typing import Callable
from marketbrief.core.models import NewsResult, Article
from marketbrief.core.enums import SourceHealth
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT

FeedFetcher = Callable[[str], str]

# Ported from v1 sources/news.py FEEDS (free/public endpoints only).
FEEDS: tuple[str, ...] = (
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "http://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "https://www.ft.com/markets?format=rss",
)


def _real_fetch(url: str) -> str:
    import requests

    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "market-brief/2.0"})
    resp.raise_for_status()
    return resp.text


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _prefix_for(url: str) -> str:
    if "cnbc" in url:
        return "cnbc"
    if "marketwatch" in url:
        return "mw"
    if "federalreserve" in url:
        return "fed"
    if "dowjones" in url or "wsj" in url:
        return "wsj"
    if "ft.com" in url:
        return "ft"
    return "rss"


def parse_feed(raw: str, *, prefix: str) -> list[Article]:
    import feedparser

    parsed = feedparser.parse(raw)
    out: list[Article] = []
    for i, entry in enumerate(parsed.entries):
        title = _clean(getattr(entry, "title", ""))
        summary = _clean(getattr(entry, "summary", getattr(entry, "description", "")))
        url = getattr(entry, "link", "")
        if not title:
            continue
        out.append(Article(source_id=f"{prefix}-{i}", title=title, summary=summary, url=url))
    return out


class RssSource:
    name = "rss"

    def __init__(self, feed_fetcher: FeedFetcher | None = None, feeds: tuple[str, ...] = FEEDS):
        self._fetch = feed_fetcher or _real_fetch
        self._feeds = feeds

    def fetch_news(self, ctx) -> NewsResult:
        if is_offline():
            return self._offline()
        articles: list[Article] = []
        for url in self._feeds:
            try:
                raw = self._fetch(url)
                articles.extend(parse_feed(raw, prefix=_prefix_for(url)))
            except Exception:
                continue  # single feed down never sinks news
        return NewsResult(name=self.name, articles=articles, health=SourceHealth.OK)

    def _offline(self) -> NewsResult:
        return NewsResult(
            name=self.name,
            articles=[Article(source_id="offline-0", title="Markets steady in quiet session",
                              summary="Offline sample article.", url="")],
            health=SourceHealth.OK,
        )
