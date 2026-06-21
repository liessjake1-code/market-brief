"""build_message attaches inline CID images as multipart/related (ported from v1).

No network: build_message only constructs the EmailMessage. send() (the SMTP path)
is exercised only for its missing-secret guard. We assert the Outlook-reliable tree
so a remote-image-blocking client still shows the charts (spec §6).
"""

from __future__ import annotations

import os

import pytest

from marketbrief.render import send as send_mod

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")


def test_html_only_message_has_no_images():
    msg = send_mod.build_message("S", "<html><body>hi</body></html>")
    cids = [p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")]
    assert cids == []


def test_inline_image_is_attached_with_cid():
    msg = send_mod.build_message(
        "S", '<html><body><img src="cid:chart_index"></body></html>',
        inline_images=[("chart_index", _PNG)],
    )
    cids = [p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")]
    assert "<chart_index>" in cids
    images = [p for p in msg.walk() if p.get_content_type() == "image/png"]
    assert len(images) == 1


def test_outlook_reliable_mime_tree_shape():
    # multipart/related[ multipart/alternative[text, html], image, image ] — images
    # are SIBLINGS of the alternative, not children of the HTML part, each inline
    # with an angle-bracketed Content-ID (the broken-chart-box fix).
    msg = send_mod.build_message(
        "S", '<html><body><img src="cid:a"><img src="cid:b"></body></html>',
        text_fallback="plain",
        inline_images=[("a", _PNG), ("b", _PNG)],
    )
    assert msg.get_content_type() == "multipart/related"
    parts = list(msg.iter_parts())
    assert parts[0].get_content_type() == "multipart/alternative"
    sub = [p.get_content_type() for p in parts[0].iter_parts()]
    assert sub == ["text/plain", "text/html"]
    images = parts[1:]
    assert [p.get_content_type() for p in images] == ["image/png", "image/png"]
    for img in images:
        assert img.get_content_disposition() == "inline"
        assert img.get("Content-ID", "").startswith("<") and img.get("Content-ID", "").endswith(">")


def test_empty_png_is_skipped():
    msg = send_mod.build_message(
        "S", "<html><body>x</body></html>", inline_images=[("empty", b"")],
    )
    images = [p for p in msg.walk() if p.get_content_type() == "image/png"]
    assert images == []


def test_missing_secret_raises():
    os.environ.pop("EMAIL_FROM", None)
    with pytest.raises(send_mod.SendConfigError):
        send_mod.build_message("S", "<html></html>")


def test_send_missing_smtp_secret_raises(monkeypatch):
    # send() must raise (not swallow) when an SMTP secret is absent, so a bad send
    # surfaces as a failed Actions run rather than a silent no-op.
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(send_mod.SendConfigError):
        send_mod.send("S", "<html></html>")
