from __future__ import annotations
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, ValidationError


class ResilienceConfig(BaseModel):
    degraded_stale_threshold: int = 2
    hard_floor_missing_threshold: int = 4


class NarrateConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    entailment_model: str = "claude-haiku-4-5"
    max_tokens: int = 1500


class ScheduleConfig(BaseModel):
    # Local-Central send window (spec §8.3). The cron window guard fires inside
    # [send_time-5min, send_window_end] once per day. The two UTC cron lines in
    # daily-brief.yml + this window cover DST.
    send_time: str = "08:30"
    send_window_end: str = "09:15"


class MonitoringConfig(BaseModel):
    # allow_repeat_send bypasses ONLY the once-per-day idempotency guard, for
    # iterating on test sends. MUST be False for go-live so retries/both DST crons
    # cannot double-send.
    allow_repeat_send: bool = False
    # Heartbeat dead-man's switch (spec §7.6): if nothing sent by this Central
    # cutoff on a trading day, alert on `heartbeat_channel`.
    heartbeat_cutoff: str = "10:00"
    heartbeat_channel: str = "telegram"


class ChartsConfig(BaseModel):
    equities: bool = True       # default on (spec §6)
    rates: bool = True          # default on
    commodities: bool = True    # default on
    vix: bool = False
    movers: bool = False
    crypto: bool = False
    scorecard: bool = False
    sparklines: bool = False    # auto-on once watchlist populated (handled in render)


class Config(BaseModel):
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    watchlist: list[str] = Field(default_factory=list)
    # Curated liquid universe the Movers board screens for winners/losers
    # (spec §7 best-effort rule). Empty -> Movers stays quiet. Do NOT screen a
    # full index live; keep this a bounded, hand-picked list.
    movers_universe: list[str] = Field(default_factory=list)
    narrate: NarrateConfig = Field(default_factory=NarrateConfig)
    charts: ChartsConfig = Field(default_factory=ChartsConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)


def load_config(path: str | Path) -> Config:
    raw_text = Path(path).read_text()
    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"config.yaml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("config.yaml must be a mapping at the top level")
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"config.yaml failed validation: {exc}") from exc
