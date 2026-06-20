from __future__ import annotations
import json
from pathlib import Path
from marketbrief.core.enums import RunMode


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def commit_state(path: str | Path, payload: dict, *, mode: RunMode) -> bool:
    """Write state ONLY on a real send. A hard no-op under NO_SEND.

    This is the single funnel for all state writes (Global Constraint).
    """
    if mode != RunMode.SEND:
        return False
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))
    return True
