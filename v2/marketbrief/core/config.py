from __future__ import annotations
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, ValidationError


class ResilienceConfig(BaseModel):
    degraded_stale_threshold: int = 2
    hard_floor_missing_threshold: int = 4


class Config(BaseModel):
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    watchlist: list[str] = Field(default_factory=list)


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
