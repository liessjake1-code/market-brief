"""brief.py — main entry: gather, build, send (spec §8.5; roadmap §5).

Pipeline as of Phase 5 (templated lines; the model arrives in Phase 6, the full
editorial template in Phase 7):

    load config + state -> pull fields -> health check
      -> hard floor? send "data unavailable" notice + exit non-zero
      -> else build a templated brief -> send (unless --no-send)
      -> on a real send: stamp state + commit back (Actions only)

LOAD-BEARING invariant (Phase 1): --no-send implies NO state write. All state
writes funnel through _commit_state(), a hard no-op under --no-send, so a test or
partial build can never poison the next day's diff or the idempotency guard.
The brief never blocks on the model or news (spec §5.6); degraded runs still ship.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import os

from engine import schedule as sch
from engine import state as state_mod
from engine.config import load_config
from render import templated
from render.send import send as smtp_send
from sources import prices
from sources.quality import Field, Source, assess

EXIT_OK = 0
EXIT_HARD_FLOOR = 2

# Test/CI seam: when MARKET_BRIEF_OFFLINE=1, skip all network pulls and synthesize
# clean placeholder fields. This lets the smoke test and the --no-send invariant
# test run deterministically without yfinance or a network, while production runs
# (env unset) always do the real pull.
_OFFLINE_ENV = "MARKET_BRIEF_OFFLINE"


def build_brief(*, send: bool, today: date | None = None) -> int:
    today = today or date.today()
    print("Daily Market Brief")
    print(f"  mode: {'FULL RUN (send + state write)' if send else 'NO-SEND (build only, no state write)'}")

    cfg = load_config()
    resilience = cfg["resilience"]

    # --- gather (Phase 5) ------------------------------------------------ #
    fields = _gather_fields()
    report = assess(
        fields,
        degraded_stale_threshold=int(resilience["degraded_stale_threshold"]),
        hard_floor_missing_threshold=int(resilience["hard_floor_missing_threshold"]),
    )
    print(f"  health: missing_core={report.missing_core} stale_core={report.stale_core} "
          f"degraded={report.degraded}")

    # --- hard floor: never ship a broken brief (spec §7.5) --------------- #
    if report.hard_floor_tripped:
        print("  hard floor TRIPPED: too many core fields missing.")
        if send:
            smtp_send(
                subject=f"Market brief unavailable — {today.isoformat()}",
                html=templated.DATA_UNAVAILABLE_HTML,
                text_fallback="Market brief unavailable: too many core fields missing.",
            )
        # Exit non-zero so the failed run is visible in Actions (spec §7.5).
        return EXIT_HARD_FLOOR

    # --- build templated brief (model + full template come later) -------- #
    lines = _templated_brief(report)
    html = _render_templated_html(today, report, lines)

    if send:
        decision = sch.decide_send(
            send_time=cfg["send_time"],
            send_window_end=cfg["send_window_end"],
            last_sent_date=_last_sent_date(),
        )
        print(f"  schedule: {decision.reason}")
        if decision.should_send:
            smtp_send(subject=_subject(today, report), html=html)
            print("  send: sent")
        else:
            print("  send: skipped by guard")
            send = False  # do not write state if we did not actually send
    else:
        print("  send: skipped (--no-send)")

    _commit_state(send=send, today=today, fields=report.fields)
    return EXIT_OK


def _gather_fields() -> dict[str, Field]:
    """Pull real fields, or synthesize clean placeholders when offline (test/CI)."""
    if os.environ.get(_OFFLINE_ENV) == "1":
        from engine.metrics import METRIC_KEYS
        return {k: Field(k, 100.0, Source.YFINANCE) for k in METRIC_KEYS}
    return prices.pull_fields()


def _templated_brief(report) -> dict[str, str]:
    """One flat line per metric from numbers + direction (no model, no causes)."""
    out: dict[str, str] = {}
    for key, field in report.fields.items():
        out[key] = templated.templated_line(field, change=None)
    return out


def _render_templated_html(today: date, report, lines: dict[str, str]) -> str:
    banner = ""
    if report.degraded:
        banner = ("<p style='background:#FBE9E7;border:1px solid #BC3B2E;padding:8px'>"
                  "Degraded run: some fields are stale or the narrative is templated.</p>")
    rows = "".join(f"<li>{line}</li>" for line in lines.values())
    return (
        "<html><body style='font-family:Georgia,serif;color:#13202E'>"
        f"<h2>Morning Market Brief</h2><p>{today:%A, %B %-d, %Y}</p>"
        f"{banner}<ul style=\"font-family:Consolas,'SFMono-Regular',monospace\">{rows}</ul>"
        "<p style='color:#6B7785'>Templated build (Phase 5). Sources: yfinance, FRED.</p>"
        "</body></html>"
    )


def _subject(today: date, report) -> str:
    tag = " [degraded]" if report.degraded else ""
    return f"Morning Market Brief — {today:%b %-d}{tag}"


def _last_sent_date() -> str | None:
    try:
        return state_mod.load_state().data.get("last_sent_date")
    except (FileNotFoundError, ValueError):
        return None


def _commit_state(*, send: bool, today: date | None = None, fields=None) -> None:
    """Single choke point for ALL state writes (spec §8.5 invariant).

    Under --no-send (or when the guard skipped the send) this is an unconditional
    no-op: no last_run.json, no last_sent_date. On a real send it stamps and
    commits state back (Actions-only PAT commit, spec §8.3).
    """
    if not send:
        print("  state: no write (no-send / not sent) [invariant]")
        return
    st = state_mod.load_state()
    if st.missing and os.environ.get(_OFFLINE_ENV) != "1":
        st = state_mod.backfill(prices.fetch_history)
    if fields:
        for key, field in fields.items():
            if field.is_usable and key in st.data["metrics"]:
                metric = st.data["metrics"][key]
                hist = list(metric.get("history", []))
                hist.append(field.value)
                metric["history"] = hist
                metric["prev_close"] = metric.get("close")
                metric["close"] = field.value
    st.data["last_sent_date"] = (today or date.today()).isoformat()
    st.data["sent_today"] = True
    state_mod.save_state(st)
    state_mod.commit_state_back()
    print("  state: written + commit-back attempted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="brief.py",
        description="Daily Market Brief: gather, build, and send the weekday brief.",
    )
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Build only: do NOT send and do NOT write state.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return build_brief(send=not args.no_send)


if __name__ == "__main__":
    sys.exit(main())
