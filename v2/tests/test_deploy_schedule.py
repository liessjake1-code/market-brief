"""Cron window + idempotency + send-time labeling (ported from v1 test_resilience).

Offline, pure datetime: the window guard fires inside the window and skips before
it / when already sent today; the live label flips from pre-market to early-session
across the 8:30 cash open.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from marketbrief.deploy import schedule as SCH

CT = ZoneInfo("America/Chicago")


def _ct(h, m):
    return datetime(2026, 6, 17, h, m, tzinfo=CT)


def test_send_inside_window():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date=None, now=_ct(8, 30))
    assert d.should_send and not d.late


def test_no_send_before_window():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date=None, now=_ct(8, 0))
    assert not d.should_send


def test_idempotent_when_already_sent_today():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date="2026-06-17", now=_ct(8, 35))
    assert not d.should_send
    assert "already sent" in d.reason


def test_allow_repeat_send_bypasses_idempotency_guard():
    # Same already-sent-today inputs, but the TEMPORARY test-iteration override
    # lets it send again. Default behavior (above) is unchanged.
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date="2026-06-17", now=_ct(8, 35),
                        allow_repeat_send=True)
    assert d.should_send
    assert "already sent" not in d.reason


def test_late_send_after_window_still_sends_flagged_late():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date=None, now=_ct(9, 40))
    assert d.should_send and d.late and d.after_open


def test_premarket_label_before_open():
    assert SCH.premarket_label(now=_ct(8, 25)).startswith("Pre-market as of")


def test_early_session_label_after_open():
    assert SCH.premarket_label(now=_ct(8, 45)).startswith("Early session as of")
