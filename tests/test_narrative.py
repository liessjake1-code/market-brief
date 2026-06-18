"""Phase 6 — matcher, cause check, news, narrative orchestration (spec §5.6 gate).

Gate slices: invented number fails to ship (retry then template); untagged cause
is stripped; quiet sections collapse; cross-asset synthesis passes when its
derived figures are in the input set; every run dumps auditable JSON.
"""

from __future__ import annotations

import json

from engine import narrative as N
from engine.matcher import (Article, MATCH_SCORE_THRESHOLD, check_cause,
                            match_section, score_article)
from sources import news


# --- matcher -------------------------------------------------------------- #
def _article(sid, title, summary=""):
    return Article(source_id=sid, title=title, summary=summary, url=f"http://x/{sid}")


def test_title_hits_weighted_double():
    a = _article("a1", "Oil surges as OPEC cuts", "crude barrel")
    score = score_article(a, ["oil", "opec", "crude", "barrel"])
    assert score > 0


def test_match_returns_top_and_filters_below_threshold():
    arts = [
        _article("a1", "Treasury yields jump after weak auction", "10-year fed rate"),
        _article("a2", "Celebrity gossip roundup", "nothing relevant here"),
    ]
    matched = match_section("rates_and_dollar", arts)
    assert matched
    assert matched[0].article.source_id == "a1"
    assert all(m.match_score >= MATCH_SCORE_THRESHOLD for m in matched)


def test_no_articles_when_all_below_threshold():
    arts = [_article("a1", "Sports recap", "team won")]
    assert match_section("commodities", arts) == []


# --- cause check ---------------------------------------------------------- #
def test_cause_check_flags_untagged_causal_claim():
    r = check_cause("Yields fell because demand was soft.", None)
    assert r.ok is False


def test_cause_check_passes_when_tagged():
    r = check_cause("Yields fell because demand was soft.", "cnbc-3")
    assert r.ok is True


def test_cause_check_passes_with_no_causal_verb():
    r = check_cause("The 10-year sits near 4.46%.", None)
    assert r.ok is True


# --- news parsing (offline, injected feed text) --------------------------- #
def test_parse_feed_extracts_title_and_summary():
    raw = """<?xml version="1.0"?><rss><channel>
      <item><title>Oil jumps on OPEC</title>
        <description>Crude rose after the cartel signaled cuts.</description>
        <link>http://ex/1</link></item>
    </channel></rss>"""
    arts = news.parse_feed(raw, prefix="cnbc")
    assert arts and arts[0].source_id == "cnbc-0"
    assert "Oil jumps" in arts[0].title


def test_fetch_articles_degrades_on_feed_failure():
    def boom(url):
        raise RuntimeError("network down")
    assert news.fetch_articles(fetcher=boom) == []


# --- _extract_json: tolerate fenced / prefixed model replies -------------- #
def test_extract_json_strips_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert json.loads(N._extract_json(raw)) == {"a": 1}


def test_extract_json_strips_bare_fence():
    raw = '```\n{"a": 1}\n```'
    assert json.loads(N._extract_json(raw)) == {"a": 1}


def test_extract_json_strips_preamble():
    raw = 'Here is the JSON you asked for:\n{"a": 1, "b": [2, 3]}'
    assert json.loads(N._extract_json(raw)) == {"a": 1, "b": [2, 3]}


def test_extract_json_leaves_clean_json_untouched():
    raw = '{"a": 1}'
    assert N._extract_json(raw) == '{"a": 1}'


# --- narrative orchestration (fake model) --------------------------------- #
def _bundles():
    section_numbers = {
        "rates_and_dollar": {"ust10y": 4.46, "spread_2s10s_bps": -25.0},
        "crypto": {"btc": 64000.0},
    }
    arts = [_article("cnbc-0", "Yields rise after soft auction", "treasury 10-year fed")]
    return N.build_bundles(section_numbers, arts)


def _fallback(section_id):
    return f"{section_id}: no clear catalyst."


def test_valid_model_output_accepted():
    # The model now writes only a number-free CAUSE; the system writes the numbers.
    def fake(system, user, model):
        return json.dumps({
            "rates_and_dollar": {
                "cause": "Yields rose on soft auction demand.",
                "cause_source_id": "cnbc-0", "confidence": "medium",
            },
            "crypto": {
                "cause": "no clear catalyst",
                "cause_source_id": None, "confidence": "low",
            },
        })
    results, degraded, raw = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake,
        templated_fallback=_fallback)
    assert not degraded
    assert not results["rates_and_dollar"].templated
    assert results["rates_and_dollar"].cause_source_id == "cnbc-0"
    # res.prose now holds the validated, number-free cause clause.
    assert results["rates_and_dollar"].prose == "Yields rose on soft auction demand."


def test_number_in_cause_falls_back_to_template_after_retry():
    # A number in the cause (the model's job is number-free) -> rejected, retried,
    # then templated. 9.99% is not in the inputs, so it is caught either way.
    calls = {"n": 0}
    def fake(system, user, model):
        calls["n"] += 1
        return json.dumps({
            "rates_and_dollar": {
                "cause": "Yields spiked to 9.99% on the auction.",
                "cause_source_id": None, "confidence": "high"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        })
    results, degraded, raw = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake,
        templated_fallback=_fallback)
    assert degraded
    assert results["rates_and_dollar"].templated
    assert "no clear catalyst" in results["rates_and_dollar"].prose
    assert calls["n"] == 2  # retried once before templating


def test_untagged_cause_is_stripped_to_template():
    def fake(system, user, model):
        return json.dumps({
            "rates_and_dollar": {  # causal verb, no source id -> cause check fails
                "cause": "Yields rose because demand was soft.",
                "cause_source_id": None, "confidence": "high"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        })
    results, degraded, raw = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake,
        templated_fallback=_fallback)
    assert results["rates_and_dollar"].templated


def test_invented_source_id_rejected():
    def fake(system, user, model):
        return json.dumps({
            "rates_and_dollar": {
                "cause": "Yields rose on soft demand.",
                "cause_source_id": "fake-999", "confidence": "high"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        })
    results, _, _ = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake,
        templated_fallback=_fallback)
    assert results["rates_and_dollar"].templated  # source id not supplied


def test_whole_call_failure_templates_all():
    def boom(system, user, model):
        raise RuntimeError("API down")
    results, degraded, raw = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=boom,
        templated_fallback=_fallback)
    assert degraded
    assert all(r.templated for r in results.values())
    assert raw is None


def test_number_free_cause_with_source_passes():
    # A clean, number-free, sourced cause is accepted (the common good case).
    def fake(system, user, model):
        return json.dumps({
            "rates_and_dollar": {
                "cause": "Yields slipped as the auction drew firm demand.",
                "cause_source_id": "cnbc-0", "confidence": "medium"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        })
    results, degraded, _ = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake,
        templated_fallback=_fallback)
    assert not results["rates_and_dollar"].templated


def test_run_dump_writes_auditable_json(tmp_path):
    results = {"crypto": N.SectionResult("crypto", "Bitcoin near 64,000.", None, "low")}
    path = N.dump_run(results, {"crypto": {}}, runs_dir=str(tmp_path), date_str="2026-06-17")
    data = json.loads(open(path).read())
    assert data["date"] == "2026-06-17"
    assert "crypto" in data["sections"]


# --- cited_sources resolution (redesign item 1: clickable per-section citation) #
def test_accepted_section_resolves_cited_source_to_title_and_url():
    def fake(system, user, model):
        return json.dumps({
            "rates_and_dollar": {
                "cause": "Yields rose on soft auction demand.",
                "cause_source_id": "cnbc-0", "confidence": "medium"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        })
    results, _, _ = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake, templated_fallback=_fallback)
    cited = results["rates_and_dollar"].cited_sources
    assert cited == ({"title": "Yields rise after soft auction", "url": "http://x/cnbc-0"},)
    # A section with no cause claim resolves to no citation (no empty source label).
    assert results["crypto"].cited_sources == ()


def test_per_section_envelope_is_unwrapped():
    # The 2026-06-18 degrade: the model wrapped the real per-section output under a
    # literal "per_section" key (echoing the schema), so every section keyed to None
    # and the whole brief fell back to templates. We must peel that envelope.
    def fake(system, user, model):
        return json.dumps({"per_section": {
            "rates_and_dollar": {
                "cause": "Yields rose on soft auction demand.",
                "cause_source_id": "cnbc-0", "confidence": "medium"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        }})
    results, degraded, _ = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake, templated_fallback=_fallback)
    assert not degraded
    assert not results["rates_and_dollar"].templated
    assert results["rates_and_dollar"].cause_source_id == "cnbc-0"


def test_flat_reply_still_accepted():
    # A correctly flat reply (keyed by section id) is unchanged by the unwrap.
    def fake(system, user, model):
        return json.dumps({
            "rates_and_dollar": {"cause": "no clear catalyst",
                                 "cause_source_id": None, "confidence": "low"},
            "crypto": {"cause": "no clear catalyst", "cause_source_id": None,
                       "confidence": "low"},
        })
    results, degraded, _ = N.generate(
        _bundles(), model="m", tolerance_pct=0.05, caller=fake, templated_fallback=_fallback)
    assert not degraded
    assert not results["rates_and_dollar"].templated


def test_wsj_and_ft_feed_prefixes():
    # Redesign item 3: WSJ feeds (Dow Jones host) and FT map to stable prefixes so
    # their source_ids are findable in runs/ and citations.
    assert news._prefix_for("https://feeds.content.dowjones.io/public/rss/RSSMarketsMain") == "wsj"
    assert news._prefix_for("https://www.ft.com/markets?format=rss") == "ft"


def test_wsj_feed_in_launch_set():
    assert any("dowjones" in u for u in news.FEEDS)
