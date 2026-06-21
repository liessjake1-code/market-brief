from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from marketbrief.core.models import BriefView

_TEMPLATE_PATH = Path(__file__).parent / "template.html.j2"

_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_PATH.parent)),
    autoescape=select_autoescape(["html", "j2", "html.j2"]),
)


def render_brief(view: BriefView) -> str:
    """Render the full brief HTML from a BriefView. Autoescaped (XSS-safe); logic-free."""
    return _ENV.get_template("template.html.j2").render(view=view)


def render_unavailable_notice() -> str:
    return (
        "<html><body><p>Market data is unavailable this morning. "
        "No brief was generated. Please check an external source directly.</p>"
        "</body></html>"
    )
