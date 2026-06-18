"""brief.py — main entry: gather, build, send.

Phase 1 stub (roadmap §1; execution guide Part 5, Phase 1). This establishes the
argparse surface and, critically, the LOAD-BEARING invariant that `--no-send`
implies NO state write from the very start (spec §8.5; CLAUDE.md):

    python brief.py --no-send   # build only, NO state write
    python brief.py             # full run, sends, writes state

Data gathering, rendering, sending, and state caching are NOT built here. They
arrive in later phases in the order the roadmap fixes. What is built now is the
*structure* that guarantees no future code path can write `last_run.json` or
touch `last_sent_date` when `--no-send` is set: state writes are funnelled
through `_commit_state()`, which is a hard no-op (and logs why) whenever the run
is in no-send mode. The guard exists before the thing it guards (Phase 2 state),
so the invariant can never be accidentally violated as state logic lands.
"""

from __future__ import annotations

import argparse
import sys


def build_brief(*, send: bool) -> int:
    """Build (and optionally send) the brief. Returns a process exit code.

    Phase 1: a stub that wires the no-send/no-state invariant and nothing else.
    Each later phase fills one slice in roadmap order. Returns 0 on success.
    """
    print("Daily Market Brief — Phase 1 stub.")
    print(f"  mode: {'FULL RUN (send + state write)' if send else 'NO-SEND (build only, no state write)'}")

    # --- gather (Phase 5) ---
    # --- top story (Phase 4) ---
    # --- diff line (Phase 3) ---
    # --- narrative (Phase 6) ---
    # --- render (Phase 7) ---
    # --- send (Phase 5/7) ---
    if send:
        # Real send path lands in later phases. Stub does not send.
        print("  send: (not implemented in Phase 1)")
    else:
        print("  send: skipped (--no-send)")

    # --- state commit (Phase 2) — funnelled through the guarded helper ---
    _commit_state(send=send)

    return 0


def _commit_state(*, send: bool) -> None:
    """Single choke point for ALL state writes (last_run.json, last_sent_date).

    The invariant lives here: under `--no-send` this is an unconditional no-op,
    so a test or partial build can never poison the next day's diff or the
    idempotency guard. Phase 2 implements the actual write INSIDE the `if send`
    branch only; the no-send branch must stay a no-op forever.
    """
    if not send:
        print("  state: no write (--no-send implies no state write) [invariant]")
        return
    # Phase 2 implements the actual last_run.json write + commit-back here.
    print("  state: (write not implemented in Phase 1)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="brief.py",
        description="Daily Market Brief: gather, build, and send the weekday brief.",
    )
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Build only: write preview HTML to disk, do NOT send and do NOT write state.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return build_brief(send=not args.no_send)


if __name__ == "__main__":
    sys.exit(main())
