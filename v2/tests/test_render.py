"""Tests for render/html.py using the current render_brief(BriefView) API.

The old render_html(sections, degraded=...) signature was removed in Task 12.
This file is rewritten to exercise render_brief and render_unavailable_notice.
"""
from marketbrief.core.enums import Direction
from marketbrief.core.models import (
    BriefView, FigureCell, GlanceRow, SectionVM, StatRow, WhyLine,
)
from marketbrief.render.html import render_brief, render_unavailable_notice


def _minimal_view(**kwargs) -> BriefView:
    sec = SectionVM(
        id="test", title="Test Section", order=0, quiet=False,
        lead=WhyLine(text="A test lead line.", hedged=False),
        stat_rows=[StatRow(label="Row", cells=[
            FigureCell(metric_label="X", value_str="1.0",
                       change_str="+0.1%", direction=Direction.UP)])],
    )
    defaults = dict(
        diff_line="X +0.1% since yesterday's close.",
        glance_rows=[GlanceRow(category="Test", latest="1.0", why_brief="Went up.")],
        sections=[sec],
        degraded=False,
        banner_text=None,
        live=None,
    )
    defaults.update(kwargs)
    return BriefView(**defaults)


def test_renders_section_titles():
    html = render_brief(_minimal_view())
    assert "Test Section" in html


def test_renders_diff_line():
    html = render_brief(_minimal_view())
    assert "X +0.1% since yesterday" in html


def test_degrade_banner_appears():
    html = render_brief(_minimal_view(degraded=True, banner_text="limited data today"))
    assert "limited data today" in html


def test_unavailable_notice_has_no_emoji_or_emdash():
    html = render_unavailable_notice()
    assert "—" not in html  # no em dash
    assert "data" in html.lower()
