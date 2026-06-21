from __future__ import annotations
from pathlib import Path
from jinja2 import Template
from marketbrief.core.models import BriefView

_TEMPLATE_PATH = Path(__file__).parent / "template.html.j2"


def render_brief(view: BriefView) -> str:
    """Render the full brief HTML from a BriefView. Logic-free: loops + conditionals only."""
    template = Template(_TEMPLATE_PATH.read_text())
    return template.render(view=view)


def render_unavailable_notice() -> str:
    return (
        "<html><body><p>Market data is unavailable this morning. "
        "No brief was generated. Please check an external source directly.</p>"
        "</body></html>"
    )
