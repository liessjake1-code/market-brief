"""Phase 7: the template renders all zones from a fixture view-model (roadmap §7).

Renders from a hand-built BriefView so the test is offline and deterministic.
Asserts the three fenced zones, the degraded banner toggle, source links, and the
favicon confinement (Movers/Watchlist only) the spec requires (§4, §6, §7).
"""

from __future__ import annotations

from render import html as html_render
from render import viewmodel as vm


def _fixture(*, degraded: bool = False) -> vm.BriefView:
    glance = (
        vm.GlanceRow(
            category="Markets",
            figures=(
                vm.FigureCell("S&P 500", "5,000", url="https://finance.yahoo.com/quote/%5EGSPC"),
            ),
            why="Indices firmer.",
        ),
        vm.GlanceRow(
            category="This morning",
            figures=(),
            why="Futures modestly higher.",
            is_live=True,
            timestamp="Pre-market as of 8:25 CT",
        ),
    )
    sections = (
        vm.SectionView("us_equities", "US Equities", "S&P 500 firmer; broad gains.", is_top_story=True),
        vm.SectionView("movers", "Movers", "NVDA led the tape.",
                       favicons=({"ticker": "NVDA", "url": "https://finance.yahoo.com/quote/NVDA",
                                  "favicon": "https://www.google.com/s2/favicons?domain=nvidia.com&sz=64"},)),
        vm.SectionView("watchlist", "Watchlist", "Watchlist is empty."),
    )
    return vm.BriefView(
        date_label="Wednesday, June 17, 2026",
        send_label="Sent Pre-market as of 8:25 CT",
        degraded=degraded,
        diff_line="S&P 500 turned higher.",
        glance_rows=glance,
        sections=sections,
        live_label="Pre-market as of 8:25 CT",
        live_figures=(vm.FigureCell("S&P futures", "+0.4%", direction="up"),),
        forward_events=({"time_label": "07:30", "title": "Initial jobless claims"},),
        earnings=({"ticker": "FDX", "when": "amc"},),
        chart_cids=("chart_index",),
    )


def test_renders_three_fenced_zones():
    html = html_render.render_brief(_fixture())
    # Settled recap (At a Glance + sections), live snapshot, forward zone all present.
    assert "At a Glance" in html
    assert "This morning so far" in html
    assert "What to Watch Today" in html
    assert "Initial jobless claims" in html


def test_live_zone_is_timestamped_and_fenced():
    html = html_render.render_brief(_fixture())
    # The live label appears and is marked as a snapshot, not a settled fact.
    assert "Pre-market as of 8:25 CT" in html
    assert "live snapshot, not a settled fact" in html


def test_top_story_marked_and_first():
    html = html_render.render_brief(_fixture())
    assert "Top Story" in html
    # Top Story section title renders before the second section.
    assert html.index("US Equities") < html.index("Movers")


def test_degraded_banner_toggles():
    assert "Degraded run" not in html_render.render_brief(_fixture(degraded=False))
    assert "Degraded run" in html_render.render_brief(_fixture(degraded=True))


def test_figures_link_to_source():
    html = html_render.render_brief(_fixture())
    assert "finance.yahoo.com/quote/%5EGSPC" in html


def test_favicons_confined_to_movers_and_watchlist():
    html = html_render.render_brief(_fixture())
    # Exactly one favicon glyph (the single Movers ticker); none in At a Glance.
    assert html.count("s2/favicons") == 1
    glance = html[html.index("At a Glance"):html.index("Top Story")]
    assert "s2/favicons" not in glance


def test_chart_cid_referenced_inline():
    html = html_render.render_brief(_fixture())
    assert 'src="cid:chart_index"' in html


def test_palette_discipline_one_accent():
    html = html_render.render_brief(_fixture())
    # The signature palette is present; green/red carry direction only.
    for hexcode in ("#13202E", "#FBFAF7", "#B0892F", "#6B7785"):
        assert hexcode in html
    assert "SFMono-Regular" in html  # tabular monospace numerals protected
