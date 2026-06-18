"""SMTP send via the transactional relay (spec §3.2, §3.3; roadmap §5).

A thin smtplib STARTTLS call so swapping providers is a credentials change, not a
rewrite (spec §13). Connects to the relay on 587, authenticates with the provider
username + API key, sets From to the verified sender and To to the Outlook address.
All values come from env/GitHub Secrets, never config or code (spec §8.4).

Send failure RAISES so a bad send shows as a failed Actions run (the heartbeat /
workflow-failure notify then fires); the caller never swallows it silently.
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
    """Build the brief message. With inline_images, the HTML part and the images
    form a multipart/related so each `cid:` reference resolves to an attachment.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _require("EMAIL_FROM")
    msg["To"] = _require("EMAIL_TO")
    msg.set_content(text_fallback or "This brief requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    for cid, png in inline_images or ():
        if not png:
            continue
        # Attach onto the HTML alternative so client treats it as related, not a
        # separate download. Content-ID is angle-bracketed; src uses the bare cid.
        html_part = msg.get_payload()[-1]
        html_part.add_related(png, maintype="image", subtype="png", cid=f"<{cid}>")
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
