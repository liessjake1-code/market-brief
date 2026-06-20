import textwrap
from pathlib import Path
import pytest
from marketbrief.core.config import load_config


def test_loads_resilience_block(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        resilience:
          degraded_stale_threshold: 2
          hard_floor_missing_threshold: 4
        watchlist: [AAPL, MSFT]
    """))
    cfg = load_config(p)
    assert cfg.resilience.degraded_stale_threshold == 2
    assert cfg.resilience.hard_floor_missing_threshold == 4
    assert cfg.watchlist == ["AAPL", "MSFT"]


def test_defaults_when_block_absent(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("watchlist: []\n")
    cfg = load_config(p)
    assert cfg.resilience.degraded_stale_threshold == 2


def test_malformed_yaml_raises_valueerror(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("resilience: [unclosed\n")
    with pytest.raises(ValueError):
        load_config(p)
