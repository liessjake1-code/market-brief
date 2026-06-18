"""Render the BriefView through the Jinja template (spec §6; roadmap §7).

Thin seam between viewmodel.BriefView and template.html.j2 so brief.py never
touches Jinja directly and the render is unit-testable from a fixture view-model.
Autoescaping is on: prose and figures are validated upstream but still pass through
HTML-escaping as defence in depth (spec §1 numbers-only model, never raw HTML).
"""

from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader, select_autoescape

from render.viewmodel import BriefView

_TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_NAME = "template.html.j2"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_brief(view: BriefView) -> str:
    """Render the full email HTML from a validated view-model."""
    return _env.get_template(_TEMPLATE_NAME).render(view=view)
