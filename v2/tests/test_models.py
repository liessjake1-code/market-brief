from marketbrief.core.models import Field, Article, NewsResult
from marketbrief.core.enums import SourceHealth


def test_field_missing_when_value_none():
    f = Field(metric="sp500", value=None, source="missing")
    assert f.is_missing is True
    assert f.is_usable is False


def test_field_usable_when_present_and_fresh():
    f = Field(metric="sp500", value=5000.0, source="yfinance")
    assert f.is_missing is False
    assert f.is_usable is True


def test_field_not_usable_when_stale():
    f = Field(metric="sp500", value=5000.0, source="yfinance", stale=True)
    assert f.is_usable is False


def test_article_defaults_blank_summary_and_url():
    a = Article(source_id="cnbc-1", title="Stocks rise")
    assert a.summary == ""
    assert a.url == ""


def test_news_result_holds_articles_and_health():
    a = Article(source_id="cnbc-1", title="Stocks rise")
    nr = NewsResult(name="rss", articles=[a])
    assert nr.health is SourceHealth.OK
    assert nr.articles[0].title == "Stocks rise"
