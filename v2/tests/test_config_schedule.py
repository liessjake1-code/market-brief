"""schedule + monitoring config blocks (cutover additions).

Defaults are production-safe (allow_repeat_send off); the real config.yaml loads
the send window and heartbeat cutoff used by the send path.
"""

from __future__ import annotations

from pathlib import Path

from marketbrief.core.config import Config, load_config

_REPO = Path(__file__).resolve().parent.parent


def test_schedule_and_monitoring_defaults():
    cfg = Config()
    assert cfg.schedule.send_time == "08:30"
    assert cfg.schedule.send_window_end == "09:15"
    assert cfg.monitoring.allow_repeat_send is False
    assert cfg.monitoring.heartbeat_cutoff == "10:00"
    assert cfg.monitoring.heartbeat_channel == "telegram"


def test_overrides_from_mapping():
    cfg = Config.model_validate({
        "schedule": {"send_time": "07:00", "send_window_end": "08:00"},
        "monitoring": {"allow_repeat_send": True, "heartbeat_cutoff": "11:30",
                       "heartbeat_channel": "github"},
    })
    assert cfg.schedule.send_time == "07:00"
    assert cfg.monitoring.allow_repeat_send is True
    assert cfg.monitoring.heartbeat_channel == "github"


def test_real_config_yaml_has_safe_defaults():
    cfg = load_config(_REPO / "config.yaml")
    # Go-live guard: the shipped config must NOT bypass the idempotency guard.
    assert cfg.monitoring.allow_repeat_send is False
    assert cfg.schedule.send_time == "08:30"
