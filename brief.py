#!/usr/bin/env python3
"""Daily Market Brief: main entry (gather, build, send).

Phase 1 (safety net) only. Later phases fill in gather/build/send. The
non-negotiable property wired in from the start: --no-send implies NO state
write, so a test build can never poison the next day's diff or the idempotency
guard (Section 2).

Usage:
    python brief.py --no-send   build only; writes a gitignored preview HTML
                                (e.g. brief_preview.html), NO state write
    python brief.py             full run: gather, build, send, write state

The no-send preview output uses a gitignored name (see .gitignore: *.preview.html
/ brief_preview.html / preview/) so test builds never get committed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Load and minimally validate config.yaml (fail fast on a boundary)."""
    if not path.exists():
        raise FileNotFoundError(f"config.yaml not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    if not isinstance(config, dict):
        raise ValueError("config.yaml did not parse to a mapping")
    return config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Market Brief")
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Build only: write HTML to disk, do NOT send and do NOT write state.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace, config: dict) -> int:
    """Drive the pipeline. Returns a process exit code.

    Phase 1 wires the control flow and the no-send/no-state contract. Each
    stage below raises until its phase is built, so nothing silently fakes
    data (Section 2: degrade, never invent).
    """
    write_state = not args.no_send  # the load-bearing contract, decided once.

    # --- gather (Phases 2, 5, 6): prices, fred, news, calendar -------------
    # --- build  (Phases 3, 4, 7): diff, top story, narrative, render -------
    # --- send/state (Phase 7 + state.py) -----------------------------------
    raise NotImplementedError(
        "Pipeline not built yet (Phase 1 safety net only). "
        f"write_state={write_state}; config keys={sorted(config)}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config()
    return run(args, config)


if __name__ == "__main__":
    sys.exit(main())
