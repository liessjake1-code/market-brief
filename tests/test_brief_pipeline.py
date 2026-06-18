"""Phase 5 — brief.py orchestration (spec §7.5, §8.5; roadmap §5 gate).

Covers the hard-floor exit and the no-state-on-no-send invariant at the
orchestration level, using the offline seam so no network is touched.
"""

from __future__ import annotations

from datetime import date

import brief as B
from sources.quality import Field, Source


def _fields(missing: set[str] | None = None) -> dict[str, Field]:
    from engine.metrics import METRIC_KEYS
    missing = missing or set()
    out = {}
    for k in METRIC_KEYS:
        if k in missing:
            out[k] = Field(k, None, Source.MISSING)
        else:
            out[k] = Field(k, 100.0, Source.YFINANCE)
    return out


def test_hard_floor_exits_nonzero_no_send(monkeypatch, tmp_path, capsys):
    # 5 missing core fields > hard_floor_missing_threshold (4) -> trip.
    monkeypatch.setattr(
        B, "_gather_fields",
        lambda: _fields({"sp500", "nasdaq", "dow", "russell", "dxy"}),
    )
    rc = B.build_brief(send=False, today=date(2026, 6, 17))
    assert rc == B.EXIT_HARD_FLOOR
    out = capsys.readouterr().out
    assert "hard floor TRIPPED" in out


def test_clean_no_send_exits_zero_and_writes_no_state(monkeypatch):
    monkeypatch.setattr(B, "_gather_fields", lambda: _fields())
    rc = B.build_brief(send=False, today=date(2026, 6, 17))
    assert rc == B.EXIT_OK


def test_commit_state_stamps_history_date_per_close(monkeypatch, tmp_path):
    # On a real (sending) run, each appended close gets today's date stamped in
    # lockstep so the chart x-axis is dated from real data going forward.
    from engine import state as S

    repo = str(tmp_path)
    monkeypatch.setattr(S, "state_path", lambda repo_root=None: f"{repo}/last_run.json")
    # Seed a small committed baseline.
    seeded = S.backfill(lambda days: {k: [100.0, 101.0] for k in __import__(
        "engine.metrics", fromlist=["METRIC_KEYS"]).METRIC_KEYS}, days=2)
    S.save_state(seeded, repo_root=repo)
    monkeypatch.setattr(B.state_mod, "commit_state_back", lambda **k: False)
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")  # backfill path no-op; load existing

    B._commit_state(send=True, today=date(2026, 6, 18), fields=_fields())

    loaded = S.load_state(repo, today=date(2026, 6, 18))
    hist = loaded.history("sp500")
    dates = loaded.history_dates("sp500")
    assert len(dates) == len(hist)          # aligned 1:1
    assert dates[-1] == "2026-06-18"        # today stamped on the new close


def test_commit_state_seeds_new_macro_metric_into_old_state(monkeypatch, tmp_path):
    # A pre-overhaul state file (no copper/inflation keys) must gain them on the
    # first real send (backward-compatible bump), so they start accruing history.
    from engine import state as S

    repo = str(tmp_path)
    monkeypatch.setattr(S, "state_path", lambda repo_root=None: f"{repo}/last_run.json")
    seeded = S.backfill(lambda days: {k: [100.0, 101.0] for k in __import__(
        "engine.metrics", fromlist=["METRIC_KEYS"]).METRIC_KEYS}, days=2)
    # Simulate an OLD file: drop the new macro keys entirely.
    for k in ("copper", "cpi_yoy", "pce_yoy", "fed_funds", "hy_spread"):
        seeded.data["metrics"].pop(k, None)
    S.save_state(seeded, repo_root=repo)
    monkeypatch.setattr(B.state_mod, "commit_state_back", lambda **k: False)
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")

    B._commit_state(send=True, today=date(2026, 6, 18), fields=_fields())

    loaded = S.load_state(repo, today=date(2026, 6, 18))
    assert loaded.history("copper") == [100.0]          # seeded + first close
    assert loaded.history("cpi_yoy") == [100.0]
    assert loaded.history_dates("copper") == ["2026-06-18"]


# --- per-stock wiring ------------------------------------------------------ #
def test_stock_universe_dedupes_watchlist_and_movers():
    cfg = {"watchlist": ["TSLA", "NVDA"], "movers_universe": ["NVDA", "AAPL"]}
    uni = B._stock_universe(cfg)
    assert uni == ["TSLA", "NVDA", "AAPL"]   # de-duped, watchlist first


def test_company_names_from_domains():
    cfg = {"ticker_domains": {"NVDA": "nvidia.com", "TSLA": "tesla.com", "X": "bad"}}
    names = B._company_names(cfg)
    assert names["NVDA"] == "nvidia"
    assert names["TSLA"] == "tesla"
    assert "X" not in names   # no dot -> skipped


def test_gather_stocks_offline_returns_empty(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    assert B._gather_stocks({"watchlist": ["NVDA"]}) == {}


def test_commit_state_appends_stock_history(monkeypatch, tmp_path):
    # A real send appends today's close/date/volume per pulled stock, seeding a
    # new ticker so it begins accruing history immediately.
    from engine import state as S
    from sources.stocks import StockQuote

    repo = str(tmp_path)
    monkeypatch.setattr(S, "state_path", lambda repo_root=None: f"{repo}/last_run.json")
    seeded = S.backfill(lambda days: {k: [100.0, 101.0] for k in __import__(
        "engine.metrics", fromlist=["METRIC_KEYS"]).METRIC_KEYS}, days=2)
    S.save_state(seeded, repo_root=repo)
    monkeypatch.setattr(B.state_mod, "commit_state_back", lambda **k: False)
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")

    quotes = {
        "NVDA": StockQuote("NVDA", 132.5, 130.0, (130.0, 132.5), ("d0", "d1"), 250_000),
    }
    B._commit_state(send=True, today=date(2026, 6, 18), fields=_fields(), stock_quotes=quotes)

    loaded = S.load_state(repo, today=date(2026, 6, 18))
    assert loaded.stock_history("NVDA") == [132.5]
    assert loaded.stock_history_dates("NVDA") == ["2026-06-18"]
    assert loaded.stock_volume("NVDA") == 250_000


def test_commit_state_no_stock_write_on_no_send(monkeypatch, tmp_path):
    # The no-send invariant covers stocks too: no state write at all.
    from engine import state as S
    from sources.stocks import StockQuote

    repo = str(tmp_path)
    monkeypatch.setattr(S, "state_path", lambda repo_root=None: f"{repo}/last_run.json")
    quotes = {"NVDA": StockQuote("NVDA", 132.5, 130.0, (130.0, 132.5), ("d0", "d1"), 1)}
    B._commit_state(send=False, today=date(2026, 6, 18), fields=_fields(), stock_quotes=quotes)
    import os
    assert not os.path.exists(f"{repo}/last_run.json")
