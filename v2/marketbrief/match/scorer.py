"""Deterministic article->section scorer (ported from v1 engine/matcher.py).

No model. Scores each candidate article by title (weight 2) + summary overlap and
attaches the top 2-3 with their numeric match_score so a weak match is visible.
An empty result pushes the model toward 'no clear catalyst' (spec §4.3, §5.6)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from marketbrief.core.models import Article
from marketbrief.match.keywords import SECTION_KEYWORDS

MATCH_SCORE_THRESHOLD = 0.15   # below this, attach no articles
TOP_ARTICLES = 3


@dataclass(frozen=True)
class ScoredArticle:
    article: Article
    match_score: float


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9&\-]+", text.lower()))


def score_article(article: Article, keywords: list[str]) -> float:
    """score = (title_hits*2 + summary_hits) / len(keywords). Title weighted 2x."""
    if not keywords:
        return 0.0
    kw = [k.lower() for k in keywords]
    title_hits = sum(1 for k in kw if k in article.title.lower())
    summary_hits = sum(1 for k in kw if k in article.summary.lower())
    return (title_hits * 2 + summary_hits) / len(kw)


def match_section(
    section_id: str,
    articles: list[Article],
    *,
    extra_keywords: list[str] | None = None,
) -> list[ScoredArticle]:
    """Top 2-3 scored articles for a section; empty if best score below threshold."""
    keywords = list(SECTION_KEYWORDS.get(section_id, [])) + list(extra_keywords or [])
    scored = [ScoredArticle(a, score_article(a, keywords)) for a in articles]
    scored = [s for s in scored if s.match_score > 0]
    scored.sort(key=lambda s: s.match_score, reverse=True)
    top = scored[:TOP_ARTICLES]
    if not top or top[0].match_score < MATCH_SCORE_THRESHOLD:
        return []
    return top


def match_sections(articles: list[Article], config) -> dict[str, list[ScoredArticle]]:
    """Run match_section for every known section; watchlist gets config tickers."""
    out: dict[str, list[ScoredArticle]] = {}
    for section_id in SECTION_KEYWORDS:
        extra = list(config.watchlist) if section_id == "watchlist" else None
        out[section_id] = match_section(section_id, articles, extra_keywords=extra)
    return out
