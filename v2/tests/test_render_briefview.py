from email.message import EmailMessage
from marketbrief.core.enums import Direction
from marketbrief.core.models import (
    BriefView, SectionVM, WhyLine, StatRow, FigureCell, GlanceRow, LiveSnapshot,
    MoverRow, MoverPeriod, MoverBoard,
)
from marketbrief.render.html import render_brief
from marketbrief.render.mime import build_message


def _view(degraded=False, banner=None, live=None):
    sec = SectionVM(id="us_equities", title="US Equities", order=1, quiet=False,
                    lead=WhyLine(text="Stocks rose on soft inflation.", hedged=False),
                    stat_rows=[StatRow(label="Indices", cells=[
                        FigureCell(metric_label="S&P", value_str="5,000",
                                   change_str="+0.4%", direction=Direction.UP,
                                   source_url="https://finance.yahoo.com/quote/%5EGSPC")])])
    return BriefView(diff_line="S&P +0.4% since yesterday's close.",
                     glance_rows=[GlanceRow(category="Markets", latest="5,000",
                                            why_brief="Stocks rose.")],
                     sections=[sec], live=live, degraded=degraded, banner_text=banner)


def test_render_contains_section_and_diff():
    html = render_brief(_view())
    # With autoescape ON, "&" in "S&P" is encoded as "&amp;" — the correct secure form.
    assert "US Equities" in html
    assert "S&amp;P" in html  # autoescape encodes & to &amp;
    assert "+0.4%" in html
    assert "5,000" in html and "finance.yahoo.com" in html


def test_no_em_dash_or_emoji():
    html = render_brief(_view())
    assert "—" not in html  # em dash


def test_degraded_banner_renders():
    html = render_brief(_view(degraded=True, banner="limited data this morning"))
    assert "limited data this morning" in html


def test_live_block_is_fenced_and_labeled():
    live = LiveSnapshot(as_of_label="Pre-market as of 08:25 CT", rows=[], is_premarket=True)
    html = render_brief(_view(live=live))
    assert "Pre-market as of 08:25 CT" in html


def test_xss_script_tag_in_section_lead_is_escaped():
    """Autoescape must neutralize script injection in model-generated prose (HIGH/XSS)."""
    payload = "<script>alert(1)</script>"
    sec = SectionVM(
        id="us_equities", title="US Equities", order=1, quiet=False,
        lead=WhyLine(text=payload, hedged=False),
        stat_rows=[],
    )
    view = BriefView(
        diff_line="", glance_rows=[], sections=[sec], live=None,
        degraded=False, banner_text=None,
    )
    html = render_brief(view)
    assert payload not in html, "Raw script tag must not appear unescaped in output"
    assert "&lt;script&gt;" in html, "Escaped form must be present"


def test_javascript_uri_source_url_is_blocked():
    """safe_url must prevent javascript: URIs from reaching rendered href (HIGH/open-redirect)."""
    from marketbrief.render.source_links import safe_url
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("data:text/html,<h1>x</h1>") is None
    assert safe_url("https://finance.yahoo.com/quote/%5EGSPC") == "https://finance.yahoo.com/quote/%5EGSPC"
    assert safe_url(None) is None


def _movers_view(board):
    sec = SectionVM(id="movers", title="Movers", order=5, quiet=False,
                    lead=WhyLine(text="Top winners and losers.", hedged=False),
                    mover_board=board)
    return BriefView(diff_line="", glance_rows=[], sections=[sec], live=None,
                     degraded=False, banner_text=None)


def test_populated_mover_board_renders_winners_and_losers():
    board = MoverBoard(periods=[MoverPeriod(
        label="Day",
        winners=[MoverRow(ticker="NVDA", favicon_url=None, value_str="+4.8%",
                          direction=Direction.UP, why="")],
        losers=[MoverRow(ticker="PFE", favicon_url=None, value_str="-3.4%",
                         direction=Direction.DOWN, why="")])])
    html = render_brief(_movers_view(board))
    assert "Day Winners" in html and "Day Losers" in html
    assert "NVDA" in html and "+4.8%" in html
    assert "PFE" in html and "-3.4%" in html


def test_empty_mover_board_renders_nothing_no_fabrication():
    """Spec §1: an empty board must produce no winners/losers UI and no names."""
    board = MoverBoard(periods=[MoverPeriod(label="Day"), MoverPeriod(label="Week")])
    html = render_brief(_movers_view(board))
    assert "Winners" not in html and "Losers" not in html


def test_none_mover_board_renders_nothing():
    html = render_brief(_movers_view(None))
    assert "Winners" not in html and "Losers" not in html


def test_dark_palette_present_in_output():
    """Regression guard: the dark-terminal palette must reach the rendered HTML."""
    html = render_brief(_view())
    assert "#0B0E14" in html  # near-black page background
    assert "#E8A33D" in html  # amber accent
    # Old cream/gold palette must be fully retired.
    assert "#FBFAF7" not in html and "#B0892F" not in html


def test_mime_has_cid_image_part():
    msg = build_message("<html><body><img src='cid:chart_index'></body></html>",
                        {"chart_index": b"\x89PNG\r\n\x1a\n"})
    assert isinstance(msg, EmailMessage)
    cids = [p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")]
    assert any("chart_index" in c for c in cids)
