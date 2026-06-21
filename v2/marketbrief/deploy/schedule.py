"""Cron-window guard, idempotency, and send-time labeling (spec §3.1, §8.3).

GitHub's scheduler runs late or skips, so an exact-minute match would silently
never fire. The guard instead fires when local Central time is inside a window
AND today has not already sent (idempotent across both DST cron lines + retries).

Pure datetime logic, no network, fully testable. The two cron lines + this window
handle DST (spec §8.3): exactly one cron fires inside the window year round.

Ported verbatim from v1 engine/schedule.py at the v2 cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
CASH_OPEN = time(8, 30)   # US cash open, 8:30 CT


@dataclass
class SendDecision:
    should_send: bool
    reason: str
    late: bool = False            # fired after the window upper bound
    after_open: bool = False       # pull happened at/after the 8:30 cash open


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def now_central(now: Optional[datetime] = None) -> datetime:
    """Current time in Central. `now` may be injected for tests (tz-aware)."""
    if now is None:
        return datetime.now(CENTRAL)
    if now.tzinfo is None:
        return now.replace(tzinfo=CENTRAL)
    return now.astimezone(CENTRAL)


def window_bounds(send_time: str, send_window_end: str) -> tuple[time, time]:
    """Lower bound is ~5 min before send_time; upper is send_window_end (spec §8.3)."""
    start = _parse_hhmm(send_time)
    # ~8:25 lower bound: five minutes before the 08:30 target (spec §8.3 "8:25").
    lower = time(start.hour, max(0, start.minute - 5))
    upper = _parse_hhmm(send_window_end)
    return lower, upper


def decide_send(
    *,
    send_time: str,
    send_window_end: str,
    last_sent_date: Optional[str],
    now: Optional[datetime] = None,
    allow_repeat_send: bool = False,
) -> SendDecision:
    """Should this run send? (spec §8.3 cron guard + idempotency)

    Fires only when local Central time is inside the window and last_sent_date is
    not today. If it somehow fires after the window, still sends but flags `late`.

    allow_repeat_send bypasses ONLY the once-per-day idempotency guard, for
    iterating on test sends. It defaults to False (production behavior: one send
    per day). RESTORE the default before go-live so the two DST crons + retries
    cannot double-send. See config monitoring.allow_repeat_send.
    """
    ct = now_central(now)
    today_str = ct.date().isoformat()

    if last_sent_date == today_str and not allow_repeat_send:
        return SendDecision(False, "already sent today (idempotent)")

    lower, upper = window_bounds(send_time, send_window_end)
    current = ct.timetz().replace(tzinfo=None)
    after_open = current >= CASH_OPEN

    if current < lower:
        return SendDecision(False, f"before window ({current:%H:%M} < {lower:%H:%M} CT)")
    if current > upper:
        # A late brief before/just after the open beats no brief (spec §8.3).
        return SendDecision(True, f"after window ({current:%H:%M} CT) — sending late",
                            late=True, after_open=after_open)
    return SendDecision(True, f"inside window ({current:%H:%M} CT)",
                        late=False, after_open=after_open)


def premarket_label(*, now: Optional[datetime] = None) -> str:
    """Label the live snapshot by ACTUAL pull time, not the schedule (spec §3.1).

    Before the 8:30 cash open: "Pre-market as of HH:MM CT". At/after open the word
    "pre-market" would be false, so it relabels to "Early session as of HH:MM CT".
    """
    ct = now_central(now)
    # %-I is platform-specific; build the stamp with %I-stripped for portability.
    hhmm = ct.strftime("%I:%M").lstrip("0")
    stamp = f"{hhmm} CT"
    if ct.timetz().replace(tzinfo=None) < CASH_OPEN:
        return f"Pre-market as of {stamp}"
    return f"Early session as of {stamp}"
