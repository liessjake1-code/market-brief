"""Phase 7: build_message attaches inline CID images as multipart/related (roadmap §7).

No network: build_message only constructs the EmailMessage. send() (the SMTP path)
is exercised elsewhere; here we assert the message structure carries the inline
images so a remote-image-blocking client still shows the charts (spec §6).
"""

from __future__ import annotations

import os

import pytest

from render import send as send_mod

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
