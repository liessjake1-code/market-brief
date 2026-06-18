"""Per-stock 'why': each surfaced ticker gets a number-free, sourced cause.

A stock in play (watchlist or a selected mover) becomes a pseudo-section keyed
'stock:<TICKER>' folded into the same single narrative call. The model writes a
number-free cause tagged to a supplied article (matched on ticker symbol +
company name); the same validator path applies, and cited_sources resolves to a
clickable citation. 'No clear catalyst' stays a correct output.
"""

from __future__ import annotations

from engine import narrative as N
from engine.matcher import Article


ARTICLES = [
    Article("cnbc-0", "Nvidia surges on new AI chip demand", "NVDA shares jumped on guidance.", "https://cnbc.com/nvda"),
    Article("cnbc-1", "Tesla deliveries beat estimates", "Tesla TSLA posted record deliveries.", "https://cnbc.com/tsla"),
    Article("cnbc-2", "Oil slips on inventory build", "Crude eased on a US build.", "https://cnbc.com/oil"),
]


def test_build_stock_bundles_keys_by_stock_id():
    bundles = N.build_stock_bundles(["NVDA", "TSLA"], ARTICLES, company_names={"NVDA": "Nvidia", "TSLA": "Tesla"})
    ids = {b.section_id for b in bundles}
    assert ids == {"stock:NVDA", "stock:TSLA"}


def test_build_stock_bundles_matches_by_ticker_and_name():
    bundles = N.build_stock_bundles(["NVDA"], ARTICLES, company_names={"NVDA": "Nvidia"})
    nvda = next(b for b in bundles if b.section_id == "stock:NVDA")
    # The Nvidia article should be matched (ticker symbol or company name keyword).
    matched_ids = {s.article.source_id for s in nvda.articles}
    assert "cnbc-0" in matched_ids
    # The unrelated oil article should not dominate.
    assert "cnbc-2" not in matched_ids


def test_build_stock_bundles_no_match_yields_empty_articles():
    bundles = N.build_stock_bundles(["ZZZZ"], ARTICLES, company_names={})
    z = bundles[0]
    assert z.articles == []   # nothing matches -> model should say no clear catalyst


def test_stock_bundles_flow_through_generate():
    # A fake model returns a number-free cause tagged to the matched article.
    def fake_caller(system, user_json, model):
        import json
        return json.dumps({
            "stock:NVDA": {"cause": "Nvidia rose after strong AI chip demand.",
                           "cause_source_id": "cnbc-0", "confidence": "high"},
        })

    bundles = N.build_stock_bundles(["NVDA"], ARTICLES, company_names={"NVDA": "Nvidia"})
    results, degraded, raw = N.generate(
        bundles, model="x", tolerance_pct=0.05,
        caller=fake_caller, templated_fallback=lambda sid: "No clear catalyst.",
    )
    res = results["stock:NVDA"]
    assert res.templated is False
    assert res.cause_source_id == "cnbc-0"
    assert res.cited_sources and res.cited_sources[0]["url"] == "https://cnbc.com/nvda"


def test_stock_cause_with_number_is_rejected():
    # A number in the cause must discard the section (numbers are Python's job).
    def numbery_caller(system, user_json, model):
        import json
        return json.dumps({
            "stock:NVDA": {"cause": "Nvidia rose 3% after the chip news.",
                           "cause_source_id": "cnbc-0", "confidence": "high"},
        })

    bundles = N.build_stock_bundles(["NVDA"], ARTICLES, company_names={"NVDA": "Nvidia"})
    results, degraded, raw = N.generate(
        bundles, model="x", tolerance_pct=0.05,
        caller=numbery_caller, templated_fallback=lambda sid: "No clear catalyst.",
    )
    assert results["stock:NVDA"].templated is True   # fell back; number rejected
    assert degraded is True


def test_stock_no_catalyst_is_accepted():
    def quiet_caller(system, user_json, model):
        import json
        return json.dumps({
            "stock:QUBT": {"cause": "no clear catalyst", "cause_source_id": None,
                           "confidence": "low"},
        })

    bundles = N.build_stock_bundles(["QUBT"], ARTICLES, company_names={})
    results, degraded, raw = N.generate(
        bundles, model="x", tolerance_pct=0.05,
        caller=quiet_caller, templated_fallback=lambda sid: "No clear catalyst.",
    )
    assert results["stock:QUBT"].templated is False   # honest uncertainty is valid
    assert results["stock:QUBT"].cause_source_id is None
