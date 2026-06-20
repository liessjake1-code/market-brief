from marketbrief.core.registry import discover_sources, discover_sections


def test_discovers_real_numeric_sources():
    names = [s.name for s in discover_sources()]
    assert "yfinance" in names
    assert "fred" in names
    assert "stooq" in names


def test_rss_not_discovered_as_datasource():
    names = [s.name for s in discover_sources()]
    assert "rss" not in names  # RssSource has fetch_news, not fetch


def test_discovers_summary_section():
    ids = [s.id for s in discover_sections()]
    assert "summary" in ids


def test_sections_sorted_by_order():
    sections = discover_sections()
    orders = [s.order for s in sections]
    assert orders == sorted(orders)
