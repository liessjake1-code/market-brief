from __future__ import annotations
from email.message import EmailMessage


def build_message(html: str, png_by_cid: dict[str, bytes]) -> EmailMessage:
    """Assemble a multipart/related message with inline CID chart images.

    No send here (spec: send path is cutover work). Pure assembly, unit-testable.
    """
    msg = EmailMessage()
    msg["Subject"] = "Daily Market Brief"
    msg.add_alternative(html, subtype="html")
    payload = msg.get_payload()[0]
    for cid, png in png_by_cid.items():
        payload.add_related(png, maintype="image", subtype="png", cid=f"<{cid}>")
    return msg
