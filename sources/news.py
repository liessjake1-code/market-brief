"""RSS news parsing (spec §5.6, §7; roadmap §6.1).

Parses headlines + the short summary each RSS item carries from CNBC markets,
MarketWatch top stories, and Fed press releases. Article-body fetching is a later
flagged enhancement (use_article_bodies in config), not in the launch build.

Network is isolated and injectable so the matcher/bundle logic is testable
offline. RSS unavailable -> [] (the explanation engine then falls back to flat
templated lines; the brief never blocks on news, spec §5.6).
"""

from __future__ import annotations

import html
import re
from typing import Callable, Optional

from engine.matcher import Article

# Verify exact feed URLs at build time (spec §7). These are the launch set.
#
# WSJ feeds are the free, public Dow Jones RSS endpoints (headline + summary only,
# which is all the explanation engine needs, spec §5.6); the full article stays
# behind the reader's own subscription. Verified resolving from the build host
# 2026-06-18. FT's public RSS is best-effort: it frequently blocks automated
# fetches, so it degrades to [] exactly like any other unreachable feed and never
# blocks the run. We add free RSS + clickable headline links ONLY — no credential
# storage or paywall scraping (HANDOFF_DESIGN: WSJ/FT decision).
FEEDS: tuple[str, ...] = (
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",       # CNBC markets
    "http://feeds.marketwatch.com/marketwatch/topstories/",         # MarketWatch top
    "https://www.federalreserve.gov/feeds/press_all.xml",           # Fed press releases
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",  # WSJ Markets (free)
    "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",    # WSJ World News (free)
    "https://www.ft.com/markets?format=rss",                        # FT Markets (best-effort)
)

# A feed fetcher returns raw feed text for a URL (injected for tests).
FeedFetcher = Callable[[str], str]
REQUEST_TIMEOUT = 15


def _fetch(url: str) -> str:
    import requests

    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "market-brief/1.0"})
    resp.raise_for_status()
    return resp.text


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")     # strip any HTML in summaries
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(raw: str, *, prefix: str) -> list[Article]:
    """Parse one feed's raw text into Articles via feedparser.

    source_id is a stable, short, per-feed-indexed tag (e.g. "cnbc-3") so the
    matcher and cause check can reference it and a human can find it in runs/.
    """
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


def fetch_articles(
    *,
    feeds: tuple[str, ...] = FEEDS,
    fetcher: Optional[FeedFetcher] = None,
) -> list[Article]:
    """Fetch + parse all feeds into a flat Article list. Failures degrade to [].

    A single feed failing never sinks the run; its articles are simply absent.
    """
    fetch = fetcher or _fetch
    articles: list[Article] = []
    for url in feeds:
        prefix = _prefix_for(url)
        try:
            raw = fetch(url)
            articles.extend(parse_feed(raw, prefix=prefix))
        except Exception:
            continue
    return articles


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
