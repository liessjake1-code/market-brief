"""Dead-man's switch decision + Telegram send (ported from v1 test_resilience).

Alerts only on a trading day after the cutoff when nothing sent; the Telegram send
is unconfigured-safe (returns False) and calls the injected sender when configured.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from marketbrief.deploy import heartbeat as HB

CT = ZoneInfo("America/Chicago")


def _ct(h, m):
    return datetime(2026, 6, 17, h, m, tzinfo=CT)


def test_heartbeat_alerts_after_cutoff_when_not_sent():
    r = HB.check(last_sent_date="2026-06-16", cutoff="10:00", channel="github",
                 is_trading_day=True, now=_ct(10, 30))
    assert r.alert is True


def test_heartbeat_no_alert_before_cutoff():
    r = HB.check(last_sent_date="2026-06-16", cutoff="10:00", channel="github",
                 is_trading_day=True, now=_ct(9, 30))
    assert r.alert is False


def test_heartbeat_no_alert_when_sent_today():
    r = HB.check(last_sent_date="2026-06-17", cutoff="10:00", channel="github",
                 is_trading_day=True, now=_ct(11, 0))
    assert r.alert is False


def test_heartbeat_no_alert_on_non_trading_day():
    r = HB.check(last_sent_date="2026-06-12", cutoff="10:00", channel="github",
                 is_trading_day=False, now=_ct(11, 0))
    assert r.alert is False


def test_telegram_send_unconfigured_returns_false(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert HB.send_telegram("hi") is False


def test_telegram_send_configured_calls_sender(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    calls = []
    assert HB.send_telegram("hi", sender=lambda tok, cid, msg: calls.append((tok, cid, msg)))
    assert calls == [("t", "c", "hi")]
