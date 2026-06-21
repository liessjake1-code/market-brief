"""Backward-compatible MIME adapter (retired in favor of render/send.py).

The real, Outlook-reliable assembly + SMTP send now lives in render/send.py
(ported from v1 at the v2 cutover). This module remains only as a thin adapter
for the original png_by_cid signature so callers/tests built against it keep
working; new code should use send.build_message / send.send directly.
"""

from __future__ import annotations

from email.message import EmailMessage

from marketbrief.render.send import build_message as _build_message

_DEFAULT_SUBJECT = "Daily Market Brief"


def build_message(html: str, png_by_cid: dict[str, bytes]) -> EmailMessage:
    """Assemble a multipart/related message with inline CID chart images.

    Delegates to the Outlook-reliable builder in render/send.py. Requires
    EMAIL_FROM / EMAIL_TO in the environment (as send.build_message does).
    """
    return _build_message(
        _DEFAULT_SUBJECT,
        html,
        inline_images=list(png_by_cid.items()),
    )
