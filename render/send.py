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
from typing import Optional

SMTP_PORT = 587
SMTP_TIMEOUT = 30


class SendConfigError(RuntimeError):
    """A required SMTP secret is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SendConfigError(f"{name} is not set (required to send)")
    return value


def build_message(subject: str, html: str, *, text_fallback: Optional[str] = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _require("EMAIL_FROM")
    msg["To"] = _require("EMAIL_TO")
    msg.set_content(text_fallback or "This brief requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")
    return msg


def send(subject: str, html: str, *, text_fallback: Optional[str] = None) -> None:
    """Send the brief. Raises on any failure so the run fails visibly."""
    host = _require("SMTP_HOST")
    user = _require("SMTP_USER")
    password = _require("SMTP_PASS")
    msg = build_message(subject, html, text_fallback=text_fallback)
    with smtplib.SMTP(host, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
