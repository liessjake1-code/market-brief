"""Phase 7 + redesign: the template renders all zones from a fixture view-model.

Renders "The Tape" (white) from a hand-built BriefView so the test is offline and
deterministic. Asserts the three fenced zones, the degraded banner toggle, source
links, per-section citations, the favicon confinement (Movers/Watchlist only),
the single What-to-Watch render, and the inline charts (spec §4, §6, §7;
HANDOFF_DESIGN).
"""

from __future__ import annotations

from render import html as html_render
from render import viewmodel as vm


def _fixture(*, degraded: bool = False) -> vm.BriefView:
    glance = (
        vm.GlanceRow(
            category="Markets",
            figures=(
                vm.FigureCell("S&P", "5,000", url="https://finance.yahoo.com/quote/%5EGSPC",
                              direction="up"),
            ),
            why="Higher on the session",
        ),
    )
    bars, maxabs = vm.build_hbars({"S&P": 0.4, "Russell": -1.2})
    sparks = vm.build_sparklines({"SPCX": [3, 4, 5, 6]})
    sections = (
        vm.SectionView(
            "us_equities", "US Equities", "S&P 500 firmer; broad gains.", is_top_story=True,
            sources=({"label": "Reuters: Stocks rise on AI optimism", "url": "https://reuters.com/x"},),
            hbars=bars, hbar_maxabs=maxabs,
        ),
        vm.SectionView(
            "commodities", "Commodities", "Oil eased on a build.",
            chart_cid="chart_oil", chart_caption="yfinance CL=F", chart_caption_url="https://yhoo/CL=F",
        ),
        vm.SectionView(
            "movers", "Movers", "NVDA led the tape.",
            favicons=({"ticker": "NVDA", "url": "https://finance.yahoo.com/quote/NVDA",
                       "favicon": "https://www.google.com/s2/favicons?domain=nvidia.com&sz=64"},)),
        vm.SectionView("watchlist", "Watchlist", "Watchlist tracked the tape.", sparklines=sparks),
    )
    return vm.BriefView(
        date_label="Wednesday, June 17, 2026",
        send_label="Sent Pre-market as of 8:25 CT",
        degraded=degraded,
        diff_line="S&P 500 turned higher.",
        glance_rows=glance,
        text_rows=(
            ("Today's events", "Initial jobless claims, 7:30 CT."),
            ("Bottom line", "Mild risk-on into data."),
        ),
        sections=sections,
        live_label="Pre-market as of 8:25 CT",
        live_figures=(vm.FigureCell("S&P futures", "+0.4%", direction="up"),),
        forward_events=({"time_label": "07:30", "title": "Initial jobless claims"},),
        earnings=({"ticker": "FDX", "when": "amc"},),
        chart_cids=("chart_oil",),
    )


def test_renders_three_fenced_zones():
    html = html_render.render_brief(_fixture())
    assert "At a Glance" in html
    assert "This morning so far" in html
    assert "What to Watch Today" in html
    assert "Initial jobless claims" in html


def test_masthead_is_the_tape():
    html = html_render.render_brief(_fixture())
    assert "The Tape" in html
    assert "Your daily market brief" in html


def test_live_zone_is_timestamped_and_fenced():
    html = html_render.render_brief(_fixture())
    assert "Pre-market as of 8:25 CT" in html
    assert "live snapshot, not a settled fact" in html


def test_top_story_marked_and_first():
    html = html_render.render_brief(_fixture())
    assert "Top Story" in html
    assert html.index("US Equities") < html.index("Commodities")


def test_degraded_banner_toggles():
    assert "Degraded run" not in html_render.render_brief(_fixture(degraded=False))
    assert "Degraded run" in html_render.render_brief(_fixture(degraded=True))


def test_figures_link_to_source():
    html = html_render.render_brief(_fixture())
    assert "finance.yahoo.com/quote/%5EGSPC" in html


def test_section_renders_clickable_source_citation():
    html = html_render.render_brief(_fixture())
    assert "Reuters: Stocks rise on AI optimism" in html
    assert "https://reuters.com/x" in html


def test_what_to_watch_renders_exactly_once():
    html = html_render.render_brief(_fixture())
    assert html.count("What to Watch Today") == 1


def test_favicons_confined_to_movers_and_watchlist():
    html = html_render.render_brief(_fixture())
    assert html.count("s2/favicons") == 1
    glance = html[html.index("At a Glance"):html.index("The Day in Full")]
    assert "s2/favicons" not in glance


def test_png_chart_referenced_inline_in_section():
    html = html_render.render_brief(_fixture())
    assert 'src="cid:chart_oil"' in html
    assert "yfinance CL=F" in html  # chart caption


def test_inline_html_charts_render():
    html = html_render.render_brief(_fixture())
    assert "Index change, week" in html  # the Top Story hbar block heading


def test_palette_discipline_white_the_tape():
    html = html_render.render_brief(_fixture())
    # The white "The Tape" palette (HANDOFF_DESIGN), one accent (chart-blue links).
    for hexcode in ("#1b1a17", "#FFFFFF", "#3a6ea5", "#8a877f"):
        assert hexcode in html
    assert "IBM Plex Mono" in html  # tabular monospace numerals protected
    assert "SFMono-Regular" in html  # web-safe mono fallback
