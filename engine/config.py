"""Load and lightly validate config.yaml (spec §8.4).

Config carries toggles, watchlist, movers universe, and the resilience /
monitoring / narrative / charts blocks. Recipient and sender are NOT here; they
are the EMAIL_TO / EMAIL_FROM secrets (single source of truth, spec §8.4).
Validation fails fast on a malformed config rather than sending a broken brief.
"""

from __future__ import annotations

import os
from typing import Any

import yaml

CONFIG_FILENAME = "config.yaml"


def config_path(repo_root: str | None = None) -> str:
    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, CONFIG_FILENAME)


def load_config(repo_root: str | None = None) -> dict[str, Any]:
    with open(config_path(repo_root), "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    _validate(cfg)
    return cfg


def _validate(cfg: Any) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("config.yaml did not parse to a mapping")
    for block in ("resilience", "monitoring", "narrative", "charts"):
        if block not in cfg or not isinstance(cfg[block], dict):
            raise ValueError(f"config.yaml missing required block: {block!r}")
    # number_tolerance_pct must be nested under narrative (spec §8.4), never top-level.
    if "number_tolerance_pct" in cfg:
        raise ValueError("number_tolerance_pct must be nested under 'narrative', not top-level")
    if "number_tolerance_pct" not in cfg["narrative"]:
        raise ValueError("narrative.number_tolerance_pct is required")
    for key in ("degraded_stale_threshold", "hard_floor_missing_threshold"):
        if key not in cfg["resilience"]:
            raise ValueError(f"resilience.{key} is required")
