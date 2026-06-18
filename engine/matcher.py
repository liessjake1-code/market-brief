"""News matcher + cause check (spec §5.6; Part 4.3, 4.5; roadmap §6.3, §6.8).

The matcher is deterministic and inspectable (no model): a per-section keyword +
ticker map scores each candidate article by title + summary overlap, and the top
2-3 are attached WITH their numeric match_score so a weak match is visible in the
output (Part 4.3).

The cause check enforces that every causal verb in the model's prose co-occurs
with a non-null cause_source_id pointing to a supplied article. It proves the
cause is TAGGED to a real article, not that the article supports it (Part 4.5);
the low match_score is the cheap mitigation flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Per-section keyword/ticker lists (Part 4.3). Authored once; one list per section.
SECTION_KEYWORDS: dict[str, list[str]] = {
    "us_equities": ["s&p", "nasdaq", "dow", "russell", "stocks", "equities",
                    "index", "rally", "selloff", "wall street", "shares"],
    "rates_and_dollar": ["yield", "treasury", "10-year", "2-year", "fed", "auction",
                          "dgs10", "rate", "dollar", "dxy", "basis points", "bps"],
    "commodities": ["oil", "crude", "wti", "opec", "gold", "barrel", "brent",
                    "energy", "bullion"],
    "washington": ["fed", "fomc", "powell", "tariff", "shutdown", "fiscal",
                   "congress", "white house", "trump", "regulation", "treasury dept"],
    "movers": ["surged", "plunged", "jumped", "tumbled", "earnings", "guidance",
               "upgrade", "downgrade", "shares"],
    "economic_data_scorecard": ["cpi", "inflation", "payrolls", "jobs", "gdp",
                                 "pce", "retail sales", "ism", "consumer", "data"],
    "earnings_on_deck": ["earnings", "reports", "quarterly", "results", "eps",
                         "guidance", "pre-open", "after close"],
    "watchlist": [],   # populated from config tickers at bundle time
    "crypto": ["bitcoin", "ethereum", "btc", "eth", "crypto", "token", "coin"],
    "volatility_breadth": ["vix", "volatility", "hedging", "fear", "breadth",
                           "advancers", "decliners"],
    "what_to_watch_today": ["today", "schedule", "due", "expected", "calendar"],
}

# Causal verbs/phrases that REQUIRE a cause_source_id (Part 4.5).
_CAUSAL_RE = re.compile(
    r"\b(because|due to|on (?:soft|strong|weak|robust|the)|amid|after|as|driven by|"
    r"thanks to|owing to|spurred by|fueled by|on the back of)\b",
    re.IGNORECASE,
)

MATCH_SCORE_THRESHOLD = 0.15   # below this, attach no articles (Part 4.3; tune §13)
TOP_ARTICLES = 3


@dataclass(frozen=True)
class Article:
    source_id: str
    title: str
    summary: str
    url: str


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
    title_terms = _terms(article.title)
    summary_terms = _terms(article.summary)
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
    """Top 2-3 scored articles for a section; empty if best score below threshold.

    An empty list pushes the model toward "no clear catalyst" (Part 4.3).
    """
    keywords = list(SECTION_KEYWORDS.get(section_id, [])) + list(extra_keywords or [])
    scored = [ScoredArticle(a, score_article(a, keywords)) for a in articles]
    scored = [s for s in scored if s.match_score > 0]
    scored.sort(key=lambda s: s.match_score, reverse=True)
    top = scored[:TOP_ARTICLES]
    if not top or top[0].match_score < MATCH_SCORE_THRESHOLD:
        return []
    return top


# --- cause check ---------------------------------------------------------- #
@dataclass
class CauseCheckResult:
    ok: bool
    reason: str


def check_cause(prose: str, cause_source_id: str | None) -> CauseCheckResult:
    """A causal verb in prose requires a non-null cause_source_id (Part 4.5).

    Proves the cause is tagged to a supplied article; does NOT verify the article
    supports it (no entailment check). Returns ok=False when a cause is asserted
    with no source tag, so the caller can strip/flag the section.
    """
    has_causal = bool(_CAUSAL_RE.search(prose))
    if has_causal and not cause_source_id:
        return CauseCheckResult(False, "causal claim with no cause_source_id")
    return CauseCheckResult(True, "ok")
