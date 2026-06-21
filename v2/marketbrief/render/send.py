"""SMTP send via the transactional relay (spec §3.2, §3.3; roadmap §5).

A thin smtplib STARTTLS call so swapping providers is a credentials change, not a
rewrite (spec §13). Connects to the relay on 587, authenticates with the provider
username + API key, sets From to the verified sender and To to the Outlook address.
All values come from env/GitHub Secrets, never config or code (spec §8.4).

Send failure RAISES so a bad send shows as a failed Actions run (the heartbeat /
workflow-failure notify then fires); the caller never swallows it silently.

Ported verbatim from v1 render/send.py at the v2 cutover. The Outlook-reliable
MIME tree (images as SIBLINGS of the alternative, not children of the HTML part)
is load-bearing: Outlook desktop will not traverse a related image nested under
the HTML sub-part (the broken-chart-box bug), but resolves cid refs against
siblings of the alternative reliably.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple

SMTP_PORT = 587
SMTP_TIMEOUT = 30

# (cid, png_bytes) pairs. The HTML references each via src="cid:<cid>"; the image
# is attached inline (multipart/related) so it renders even with remote images off.
InlineImage = Tuple[str, bytes]


class SendConfigError(RuntimeError):
    """A required SMTP secret is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SendConfigError(f"{name} is not set (required to send)")
    return value


def build_message(
    subject: str,
    html: str,
    *,
    text_fallback: Optional[str] = None,
    inline_images: Optional[Iterable[InlineImage]] = None,
) -> EmailMessage:
    """Build the brief message in the Outlook-reliable MIME shape.

    With inline images the tree is:

        multipart/related
          multipart/alternative
            text/plain
            text/html
          image/png   (inline, Content-ID <cid>)
          image/png   ...

    The images are SIBLINGS of the alternative, not children of the HTML part.
    Outlook desktop often will not traverse a related image nested under the HTML
    sub-part (the broken-chart-box bug, HANDOFF_DESIGN CID fix), but it resolves
    `cid:` references against siblings of the alternative reliably. Each image is
    marked Content-Disposition: inline with an angle-bracketed Content-ID; the HTML
    `src="cid:<cid>"` uses the bare cid.

    With no inline images we keep the simple alternative(text, html) tree.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _require("EMAIL_FROM")
    msg["To"] = _require("EMAIL_TO")

    images = [(cid, png) for cid, png in (inline_images or ()) if png]
    text = text_fallback or "This brief requires an HTML-capable client."

    if not images:
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        return msg

    # Build the inner text/html alternative first, then make the top message a
    # multipart/related whose first part is that alternative and whose remaining
    # parts are the images (siblings of the alternative, the Outlook-reliable tree).
    alt = EmailMessage()
    alt.set_content(text)
    alt.add_alternative(html, subtype="html")

    msg.set_content("See the HTML part for this brief.")  # seed a payload, replaced below
    msg.make_mixed()
    msg.set_type("multipart/related")
    msg.set_payload([])  # drop the seed; rebuild children explicitly
    msg.attach(alt)
    for cid, png in images:
        img = EmailMessage()
        img.set_content(
            png,
            maintype="image",
            subtype="png",
            cid=f"<{cid}>",
            disposition="inline",
        )
        msg.attach(img)
    return msg


def send(
    subject: str,
    html: str,
    *,
    text_fallback: Optional[str] = None,
    inline_images: Optional[Iterable[InlineImage]] = None,
) -> None:
    """Send the brief. Raises on any failure so the run fails visibly."""
    host = _require("SMTP_HOST")
    user = _require("SMTP_USER")
    password = _require("SMTP_PASS")
    msg = build_message(subject, html, text_fallback=text_fallback, inline_images=inline_images)
    with smtplib.SMTP(host, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
