"""Per-stock state namespace (watchlist + movers feature).

A separate `stocks` map in last_run.json holds per-ticker close/history/volume,
kept apart from the macro `metrics` map. Backward compatible: an older state
file with no `stocks` key loads cleanly and the accessors return empty.

What this covers:
  - State.stocks / stock_history / stock_history_dates accessors (empty-safe).
  - _empty_state seeds an empty stocks map; _empty_stock scaffold shape.
  - save_state trims stock history + dates to STOCK_HISTORY_KEEP in lockstep.
  - seed_stock_state folds a new ticker into an existing state (commit-back path).
  - Old state files without a stocks key still load (no schema bump).
"""

from __future__ import annotations

import json
import os
from datetime import date

import pytest

from engine import state as S


@pytest.fixture
def repo(tmp_path):
    return str(tmp_path)


# --- empty state seeds a stocks map --------------------------------------- #
def test_empty_state_has_stocks_map(repo):
    st = S.load_state(repo)  # missing -> empty
    assert st.stocks == {}


# --- accessors are empty-safe --------------------------------------------- #
def test_stock_accessors_empty_when_absent(repo):
    st = S.load_state(repo)
    assert st.stock_history("NVDA") == []
    assert st.stock_history_dates("NVDA") == []
    assert st.stock_volume("NVDA") is None


def test_stock_accessors_return_stored_values():
    data = S._empty_state()
    data["stocks"]["NVDA"] = {
        "close": 132.5,
        "prev_close": 130.0,
        "history": [128.0, 130.0, 132.5],
        "history_dates": ["2026-06-16", "2026-06-17", "2026-06-18"],
        "volume": 250_000,
        "change_pct": 1.92,
    }
    st = S.State(data=data, path="x")
    assert st.stock_history("NVDA") == [128.0, 130.0, 132.5]
    assert st.stock_history_dates("NVDA") == ["2026-06-16", "2026-06-17", "2026-06-18"]
    assert st.stock_volume("NVDA") == 250_000


# --- _empty_stock scaffold shape ------------------------------------------ #
def test_empty_stock_scaffold_shape():
    sk = S._empty_stock()
    assert sk["close"] is None
    assert sk["prev_close"] is None
    assert sk["history"] == []
    assert sk["history_dates"] == []
    assert sk["volume"] is None
    assert sk["change_pct"] is None  # stocks always use percent change, never bps


# --- save trims stock history to STOCK_HISTORY_KEEP in lockstep ----------- #
def test_save_trims_stock_history_in_lockstep(repo):
    data = S._empty_state()
    n = S.STOCK_HISTORY_KEEP + 8
    data["stocks"]["NVDA"] = {
        **S._empty_stock(),
        "history": [100.0 + i for i in range(n)],
        "history_dates": [f"d{i}" for i in range(n)],
    }
    st = S.State(data=data, path=S.state_path(repo))
    st.data["last_sent_date"] = "2026-06-18"
    S.save_state(st, repo_root=repo)
    loaded = S.load_state(repo, today=date(2026, 6, 18))
    assert len(loaded.stock_history("NVDA")) == S.STOCK_HISTORY_KEEP
    assert len(loaded.stock_history_dates("NVDA")) == S.STOCK_HISTORY_KEEP
    # Lockstep: the trimmed tail keeps the most-recent closes/dates aligned.
    assert loaded.stock_history("NVDA")[-1] == 100.0 + (n - 1)
    assert loaded.stock_history_dates("NVDA")[-1] == f"d{n - 1}"


def test_stock_history_keep_is_ten():
    # The committed-file-size decision: 10 closes per stock (see plan).
    assert S.STOCK_HISTORY_KEEP == 10


# --- seed_stock_state folds a new ticker into existing state -------------- #
def test_seed_stock_state_adds_missing_ticker():
    data = S._empty_state()  # no stocks yet
    S.seed_stock_state(data, "QUBT")
    assert "QUBT" in data["stocks"]
    assert data["stocks"]["QUBT"] == S._empty_stock()


def test_seed_stock_state_leaves_existing_ticker_untouched():
    data = S._empty_state()
    data["stocks"]["NVDA"] = {**S._empty_stock(), "close": 132.5, "history": [132.5]}
    S.seed_stock_state(data, "NVDA")
    # Existing data must not be clobbered by a seed.
    assert data["stocks"]["NVDA"]["close"] == 132.5
    assert data["stocks"]["NVDA"]["history"] == [132.5]


# --- backward compatibility: no stocks key still loads -------------------- #
def test_old_state_without_stocks_key_loads(repo):
    # Simulate a pre-feature state file: valid metrics, NO stocks key.
    path = S.state_path(repo)
    data = S._empty_state()
    data.pop("stocks", None)
    data["last_sent_date"] = "2026-06-17"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    loaded = S.load_state(repo, today=date(2026, 6, 18))
    assert loaded.missing is False
    assert loaded.stocks == {}            # empty-safe, no raise
    assert loaded.stock_history("NVDA") == []


def test_save_round_trips_stocks(repo):
    data = S._empty_state()
    data["stocks"]["TSLA"] = {
        **S._empty_stock(),
        "close": 245.0,
        "prev_close": 240.0,
        "history": [240.0, 245.0],
        "history_dates": ["2026-06-17", "2026-06-18"],
        "volume": 80_000,
        "change_pct": 2.08,
    }
    st = S.State(data=data, path=S.state_path(repo))
    st.data["last_sent_date"] = "2026-06-18"
    S.save_state(st, repo_root=repo)
    loaded = S.load_state(repo, today=date(2026, 6, 18))
    assert loaded.stocks["TSLA"]["close"] == 245.0
    assert loaded.stock_volume("TSLA") == 80_000
