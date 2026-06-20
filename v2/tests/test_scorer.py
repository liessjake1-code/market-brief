from marketbrief.core.models import Article
from marketbrief.match.scorer import (
    score_article, match_section, ScoredArticle, MATCH_SCORE_THRESHOLD, TOP_ARTICLES,
)
from marketbrief.match.keywords import SECTION_KEYWORDS, CAUSAL_RE


def _a(title, summary=""):
    return Article(source_id="x-1", title=title, summary=summary)


def test_title_hits_weighted_double_over_summary():
    kw = ["oil", "opec"]
    title_only = score_article(_a("Oil jumps", ""), kw)      # 1 title hit -> 2/2
    summary_only = score_article(_a("Markets", "oil up"), kw) # 1 summary hit -> 1/2
    assert title_only == 1.0
    assert summary_only == 0.5


def test_empty_keywords_scores_zero():
    assert score_article(_a("anything"), []) == 0.0


def test_match_section_returns_top_n_sorted_desc():
    arts = [
        _a("Oil and crude and opec and wti", "barrel brent"),  # high
        _a("Oil edges up", ""),                                 # mid
        _a("Quiet markets", ""),                                # zero -> dropped
    ]
    out = match_section("commodities", arts)
    assert all(isinstance(s, ScoredArticle) for s in out)
    assert len(out) <= TOP_ARTICLES
    assert out[0].match_score >= out[-1].match_score
    assert all(s.article.title != "Quiet markets" for s in out)


def test_below_threshold_best_returns_empty():
    # one weak summary hit across a long keyword list -> below 0.15
    arts = [_a("Totally unrelated headline", "mentions oil once")]
    out = match_section("commodities", arts)
    assert out == []


def test_keyword_table_and_regex_present():
    assert "us_equities" in SECTION_KEYWORDS
    assert CAUSAL_RE.search("yields fell on soft demand")
    assert not CAUSAL_RE.search("yields were unchanged today")


from marketbrief.match.scorer import match_sections
from marketbrief.core.config import Config


def test_match_sections_covers_every_section():
    arts = [_a("Oil and crude and opec spike", "barrel brent energy")]
    out = match_sections(arts, Config())
    assert set(out.keys()) == set(SECTION_KEYWORDS.keys())
    assert any(out["commodities"])  # the oil article landed in commodities


def test_watchlist_uses_config_tickers():
    arts = [_a("NVDA NVDA NVDA surges on guidance", "nvda")]
    out = match_sections(arts, Config(watchlist=["nvda"]))
    assert any(out["watchlist"])
