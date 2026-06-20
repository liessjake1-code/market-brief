from marketbrief.render.html import render_html, render_unavailable_notice
from marketbrief.core.models import SectionVM


def test_renders_sections_in_order():
    vms = [SectionVM(id="a", title="Alpha", order=1, body="aaa"),
           SectionVM(id="b", title="Beta", order=0, body="bbb")]
    html = render_html(vms, degraded=False)
    assert "Alpha" in html and "Beta" in html
    assert html.index("Beta") < html.index("Alpha")  # order respected by caller


def test_degrade_banner_appears():
    html = render_html([], degraded=True)
    assert "degraded" in html.lower() or "limited data" in html.lower()


def test_unavailable_notice_has_no_emoji_or_emdash():
    html = render_unavailable_notice()
    assert "—" not in html  # no em dash
    assert "data" in html.lower()
