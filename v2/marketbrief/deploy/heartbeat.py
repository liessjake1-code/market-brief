"""Dead-man's switch (spec §7.6; roadmap §5.13).

Every resilience mechanism fires only WHEN the brief runs; none fire when it
stops running entirely, which is the failure most likely to end the project
silently. The heartbeat is a check on an INDEPENDENT channel: on a trading day,
if last_sent_date is not today by a cutoff, something is wrong and an alert fires.

Channels:
  - "github": rely on GitHub's built-in notify-on-workflow-failure. The heartbeat
    job simply exits non-zero when a miss is detected, which surfaces as a failed
    run in your inbox without depending on the (possibly broken) email path.
  - "telegram": post to a bot via TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.

Pure decision logic here (alert or not, and the message); the actual Telegram
send is isolated and injectable so it is testable offline.

Ported verbatim from v1 engine/heartbeat.py at the v2 cutover.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import requests

CENTRAL = ZoneInfo("America/Chicago")
REQUEST_TIMEOUT = 15


@dataclass
class HeartbeatResult:
    alert: bool
    message: str
    channel: str


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def check(
    *,
    last_sent_date: Optional[str],
    cutoff: str,
    channel: str,
    is_trading_day: bool,
    now: Optional[datetime] = None,
) -> HeartbeatResult:
    """Decide whether to alert (spec §7.6).

    Alerts only on a trading day, only once the local cutoff has passed, and only
    when last_sent_date is not today. A weekend/holiday never alerts.
    """
    ct = (now or datetime.now(CENTRAL)).astimezone(CENTRAL)
    today_str = ct.date().isoformat()

    if not is_trading_day:
        return HeartbeatResult(False, "non-trading day; no heartbeat expected", channel)
    if last_sent_date == today_str:
        return HeartbeatResult(False, "brief already sent today", channel)
    if ct.timetz().replace(tzinfo=None) < _parse_hhmm(cutoff):
        return HeartbeatResult(False, f"before cutoff {cutoff} CT; still time to send", channel)

    msg = (
        f"Market brief heartbeat MISS: no send recorded for {today_str} "
        f"by {cutoff} CT (last_sent_date={last_sent_date}). Check the workflow."
    )
    return HeartbeatResult(True, msg, channel)


def send_telegram(
    message: str,
    *,
    sender: Optional[Callable[[str, str, str], None]] = None,
) -> bool:
    """Post an alert to Telegram. Returns False (not raises) if unconfigured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    do_send = sender or _post_telegram
    try:
        do_send(token, chat_id, message)
        return True
    except Exception:
        return False


def _post_telegram(token: str, chat_id: str, message: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=REQUEST_TIMEOUT,
    ).raise_for_status()
