from __future__ import annotations
import sys
import traceback
from typing import Callable, TypeVar

T = TypeVar("T")


def run_isolated(label: str, fn: Callable[[], T], fallback: T) -> tuple[T, str | None]:
    """Run fn in isolation. On any exception, log with context and return fallback.

    Never silently swallows: the label + traceback go to stderr (Global Constraint).
    """
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 - intentional plugin firewall
        print(f"[isolated:{label}] failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return fallback, str(exc)
