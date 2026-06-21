"""brief.py — v2 main entry: build, then (optionally) send (spec §8.5; cutover).

Pipeline:

    load config + state -> run pipeline -> hard floor? unavailable notice + exit 2
      -> render HTML + inline charts
      -> NO_SEND: write preview, NO send, NO state write (the load-bearing invariant)
      -> SEND: schedule-window guard -> SMTP send -> stamp + commit state
               -> heartbeat on a missed/failed send

LOAD-BEARING invariant (CLAUDE.md / spec §8.5): --no-send implies NO state write.
All state writes funnel through core.state.commit_state (a hard no-op under
NO_SEND) AND only fire after an actual SMTP send. A build or a guard-skipped run
never poisons the next day's diff or the once-per-day idempotency guard.

The brief never blocks on the model or news (spec §5.6): the pipeline degrades to
templated lines and still ships. Send failure RAISES (render/send.send) so a bad
send shows as a failed Actions run; the heartbeat is an independent dead-man check.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from marketbrief.core.enums import RunMode
from marketbrief.core.config import load_config, Config
from marketbrief.core.context import BriefContext
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.state import load_state, commit_state
from marketbrief.render.html import render_brief, render_unavailable_notice
from marketbrief.render.send import send as smtp_send
from marketbrief.deploy import schedule as sch
from marketbrief.deploy import heartbeat as hb
from marketbrief.deploy.state_commit import commit_state_back

EXIT_OK = 0
EXIT_HARD_FLOOR = 2

_PREVIEW_PATH = "brief.preview.html"


def build_brief(
    *, mode: RunMode, config_path, state_path, today: date | None = None
) -> tuple[int, str, BriefContext | None]:
    """Build the brief. PURE: renders HTML, never sends, never writes state.

    Returns (exit_code, html, ctx). ctx is None on the hard floor (no brief built).
    State writes + sends are the orchestrator's job (run_send), so the no-send
    invariant cannot be violated here regardless of mode.
    """
    today = today or date.today()
    config = load_config(config_path)
    prev_state = load_state(state_path)
    ctx = BriefContext(run_date=today, mode=mode, config=config, prev_state=prev_state)
    ctx = run_pipeline(ctx)

    if ctx.health.hard_floor_tripped:
        return EXIT_HARD_FLOOR, render_unavailable_notice(), None

    html = render_brief(ctx.brief_view)
    return EXIT_OK, html, ctx


def _subject(today: date, degraded: bool) -> str:
    tag = " [degraded]" if degraded else ""
    return f"Morning Market Brief — {today:%b %-d}{tag}"


def _png_items(ctx: BriefContext) -> list[tuple[str, bytes]]:
    view = ctx.brief_view
    if view is None:
        return []
    return list(view.png_by_cid.items())


def _last_sent_date(prev_state: dict) -> str | None:
    return (prev_state or {}).get("last_sent_date")


def _allow_repeat(config: Config) -> bool:
    """Whether to bypass the once-per-day idempotency guard.

    A PER-INVOCATION env override (MARKET_BRIEF_ALLOW_REPEAT=1) for a one-off manual
    second send, so the committed config stays false and the bypass can never get
    stuck `true` across deploys (a stale committed `true` would let the two DST crons
    + Actions retries double-send every day). Config remains a fallback for parity.
    """
    if os.environ.get("MARKET_BRIEF_ALLOW_REPEAT") == "1":
        return True
    return config.monitoring.allow_repeat_send


def _state_payload(prev_state: dict, today: date) -> dict:
    """The state to write on a real send: prior keys + today's stamps.

    Preserves any existing keys (e.g. cached fields) and stamps last_sent_date /
    run_date so the next run's idempotency guard and diff see today.
    """
    return {
        **(prev_state or {}),
        "run_date": today.isoformat(),
        "last_sent_date": today.isoformat(),
    }


def run_send(
    *,
    mode: RunMode,
    config_path,
    state_path,
    today: date | None = None,
    smtp_sender=smtp_send,
    now=None,
) -> int:
    """Build, then send + commit state on a real SEND that the guard allows.

    smtp_sender / now are injectable so the send path is testable offline. On
    NO_SEND we write the preview and return without touching state or the network.
    """
    today = today or date.today()
    config = load_config(config_path)
    code, html, ctx = build_brief(
        mode=mode, config_path=config_path, state_path=state_path, today=today
    )

    if code == EXIT_HARD_FLOOR:
        # Too much core data missing: send the unavailable notice (real send only),
        # never write state, and exit non-zero so the failed run is visible.
        if mode == RunMode.SEND:
            _send_unavailable(html, today, smtp_sender)
        print(f"mode={mode.value} exit={code} HARD FLOOR (no state write)")
        return code

    degraded = bool(ctx.brief_view.degraded)

    if mode != RunMode.SEND:
        Path(_PREVIEW_PATH).write_text(html)
        print(f"mode={mode.value} exit={code} bytes={len(html)} preview={_PREVIEW_PATH} (no send, no state)")
        return code

    # --- SEND path ---------------------------------------------------------- #
    decision = sch.decide_send(
        send_time=config.schedule.send_time,
        send_window_end=config.schedule.send_window_end,
        last_sent_date=_last_sent_date(ctx.prev_state),
        now=now,
        allow_repeat_send=_allow_repeat(config),
    )
    print(f"  schedule: {decision.reason}")

    if not decision.should_send:
        # Guard skipped the send: NO send, NO state write. The heartbeat (run
        # separately / on a later invocation) is what catches a true day-long miss.
        print(f"mode={mode.value} exit={code} send skipped by guard (no state write)")
        return code

    smtp_sender(
        _subject(today, degraded),
        html,
        inline_images=_png_items(ctx),
    )
    print(f"  send: sent ({len(_png_items(ctx))} inline chart(s))")

    # Only now that the send succeeded do we stamp + commit state (single funnel).
    commit_state(state_path, _state_payload(ctx.prev_state, today), mode=mode)
    commit_state_back()
    print(f"mode={mode.value} exit={code} sent + state committed")
    return code


def _send_unavailable(html: str, today: date, smtp_sender) -> None:
    smtp_sender(
        f"Market brief unavailable — {today.isoformat()}",
        html,
        text_fallback="Market brief unavailable: too many core fields missing.",
    )


def heartbeat_check(*, config_path, state_path, is_trading_day: bool, now=None) -> int:
    """Independent dead-man's switch (spec §7.6). Returns non-zero on a miss.

    Run as its own step/invocation: if nothing sent by the Central cutoff on a
    trading day, alert on the configured channel and exit non-zero so a failed run
    surfaces in the inbox even if the email path itself is broken.
    """
    config: Config = load_config(config_path)
    prev_state = load_state(state_path)
    result = hb.check(
        last_sent_date=_last_sent_date(prev_state),
        cutoff=config.monitoring.heartbeat_cutoff,
        channel=config.monitoring.heartbeat_channel,
        is_trading_day=is_trading_day,
        now=now,
    )
    print(f"  heartbeat: {result.message}")
    if not result.alert:
        return EXIT_OK
    if result.channel == "telegram":
        hb.send_telegram(result.message)
    return 1  # surface as a failed run


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Market Brief v2")
    parser.add_argument("--no-send", action="store_true",
                        help="build only, no send, no state write")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--state", default="last_run.json")
    args = parser.parse_args(argv)
    mode = RunMode.NO_SEND if args.no_send else RunMode.SEND
    return run_send(mode=mode, config_path=args.config, state_path=args.state)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
