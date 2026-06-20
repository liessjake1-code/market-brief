from __future__ import annotations
from jinja2 import Template
from marketbrief.core.models import SectionVM

_TEMPLATE = Template(
    """<html><body>
{% if degraded %}<p class="banner">Some sources returned limited data or could not be refreshed this morning.</p>{% endif %}
{% for s in sections %}<section><h2>{{ s.title }}</h2><p>{{ s.body }}</p></section>
{% endfor %}</body></html>"""
)


def render_html(sections: list[SectionVM], *, degraded: bool) -> str:
    ordered = sorted(sections, key=lambda v: v.order)
    return _TEMPLATE.render(sections=ordered, degraded=degraded)


def render_unavailable_notice() -> str:
    return (
        "<html><body><p>Market data is unavailable this morning. "
        "No brief was generated. Please check an external source directly.</p>"
        "</body></html>"
    )
