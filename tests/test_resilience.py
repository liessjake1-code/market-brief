"""Phase 5 — resilience + data layer (spec §7.5, §3.1, §8.3, §7.6; roadmap §5 gate).

Gate slices covered offline: stale fields excluded; degraded banner trips; hard
floor on too-many-missing; FRED yield fallback; oil prefers stale over a lagging
FRED print; cron window + idempotency; pre-market vs early-session label;
heartbeat alerts within the day. The live-mornings half of the gate is Track A.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from engine import heartbeat as HB
from engine import schedule as SCH
from sources import prices as P
from sources.quality import Field, Source, assess
from sources.symbols import CORE_FIELDS

CT = ZoneInfo("America/Chicago")


# --- health check / degraded / hard floor --------------------------------- #
def _all_good_fields() -> dict[str, Field]:
    return {k: Field(k, 100.0, Source.YFINANCE) for k in
            ("sp500", "nasdaq", "dow", "russell", "vix", "wti", "gold",
             "dxy", "ust10y", "ust2y", "btc", "eth")}


def test_clean_run_not_degraded_not_floored():
    r = assess(_all_good_fields(), degraded_stale_threshold=2,
               hard_floor_missing_threshold=4)
    assert not r.degraded and not r.hard_floor_tripped
    assert r.missing_core == [] and r.stale_core == []


def test_two_stale_core_trips_degraded():
    f = _all_good_fields()
    f["sp500"].stale = True
    f["wti"].stale = True
    r = assess(f, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert r.degraded is True
    assert r.hard_floor_tripped is False


def test_model_failure_trips_degraded_even_when_data_clean():
    r = assess(_all_good_fields(), degraded_stale_threshold=2,
               hard_floor_missing_threshold=4, model_failed=True)
    assert r.degraded is True


def test_hard_floor_on_more_than_threshold_missing_core():
    f = _all_good_fields()
    for k in ("sp500", "nasdaq", "dow", "russell", "dxy"):  # 5 missing > 4
        f[k] = Field(k, None, Source.MISSING)
    r = assess(f, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert r.hard_floor_tripped is True


def test_nan_value_counts_as_missing_core():
    f = _all_good_fields()
    f["sp500"] = Field("sp500", float("nan"), Source.YFINANCE)
    r = assess(f, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert "sp500" in r.missing_core


def test_stale_keys_exclude_set_for_downstream_engines():
    f = _all_good_fields()
    f["wti"].stale = True
    r = assess(f, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert "wti" in r.stale_keys  # diff/top_story/narrative will exclude it


# --- yield FRED fallback + oil last-resort -------------------------------- #
def test_yield_uses_fred_primary():
    def fake_series(series_id, limit):
        return [("2026-06-15", 4.2), ("2026-06-16", 4.28)]
    fields = P.pull_fields(downloader=lambda s, d: [], series_fetcher=fake_series)
    assert fields["ust10y"].source is Source.FRED
    assert fields["ust10y"].value == 4.28


def test_oil_prefers_stale_over_lagging_fred():
    """yfinance oil missing -> FRED only as a dated, stale last resort (Decision 14)."""
    def fake_series(series_id, limit):
        return [("2026-06-10", 74.0)]  # several days stale
    fields = P.pull_fields(downloader=lambda s, d: [], series_fetcher=fake_series)
    wti = fields["wti"]
    assert wti.source is Source.FRED_LAST_RESORT
    assert wti.stale is True
    assert wti.as_of == "2026-06-10"


def test_oil_yfinance_primary_when_available():
    def dl(symbol, days):
        return [70.0, 71.0, 72.5] if symbol == "CL=F" else []
    fields = P.pull_fields(downloader=dl, series_fetcher=lambda *a: [])
    assert fields["wti"].source is Source.YFINANCE
    assert fields["wti"].value == 72.5


def test_missing_everything_marks_missing():
    fields = P.pull_fields(downloader=lambda s, d: [], series_fetcher=lambda *a: [])
    assert fields["sp500"].is_missing
    assert fields["sp500"].source is Source.MISSING


# --- backfill history sourcing -------------------------------------------- #
def test_select_close_handles_multiindex_frame():
    """yfinance==1.4.1 returns ('Close', symbol) MultiIndex columns (spec §13).

    Guards the load-bearing-pin failure mode: a column-shape change silently
    zeroing every pull. Builds the frame shape yfinance actually returns.
    """
    import pandas as pd

    from sources import prices as P

    df = pd.DataFrame(
        {("Close", "^GSPC"): [1.0, 2.0, 3.0], ("Open", "^GSPC"): [1.0, 2.0, 3.0]}
    )
    close = P._select_close(df, "^GSPC")
    assert close is not None
    assert list(close) == [1.0, 2.0, 3.0]


def test_select_close_handles_flat_frame():
    import pandas as pd

    from sources import prices as P

    df = pd.DataFrame({"Close": [4.0, 5.0], "Open": [4.0, 5.0]})
    close = P._select_close(df, "AAPL")
    assert list(close) == [4.0, 5.0]


def test_fetch_history_sources_yields_from_fred():
    def dl(symbol, days):
        return [1.0, 2.0, 3.0]
    def fake_series(series_id, limit):
        return [("d1", 4.1), ("d2", 4.2)]
    hist = P.fetch_history(20, downloader=dl, series_fetcher=fake_series)
    assert hist["ust10y"] == [4.1, 4.2]   # FRED-sourced
    assert hist["sp500"] == [1.0, 2.0, 3.0]  # yfinance-sourced


# --- cron window + idempotency -------------------------------------------- #
def _ct(h, m):
    return datetime(2026, 6, 17, h, m, tzinfo=CT)


def test_send_inside_window():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date=None, now=_ct(8, 30))
    assert d.should_send and not d.late


def test_no_send_before_window():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date=None, now=_ct(8, 0))
    assert not d.should_send


def test_idempotent_when_already_sent_today():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date="2026-06-17", now=_ct(8, 35))
    assert not d.should_send
    assert "already sent" in d.reason


def test_allow_repeat_send_bypasses_idempotency_guard():
    # Same already-sent-today inputs, but the TEMPORARY test-iteration override
    # lets it send again. Default behavior (above) is unchanged.
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date="2026-06-17", now=_ct(8, 35),
                        allow_repeat_send=True)
    assert d.should_send
    assert "already sent" not in d.reason


def test_late_send_after_window_still_sends_flagged_late():
    d = SCH.decide_send(send_time="08:30", send_window_end="09:15",
                        last_sent_date=None, now=_ct(9, 40))
    assert d.should_send and d.late and d.after_open


def test_premarket_label_before_open():
    assert SCH.premarket_label(now=_ct(8, 25)).startswith("Pre-market as of")


def test_early_session_label_after_open():
    assert SCH.premarket_label(now=_ct(8, 45)).startswith("Early session as of")


# --- heartbeat ------------------------------------------------------------ #
def test_heartbeat_alerts_after_cutoff_when_not_sent():
    r = HB.check(last_sent_date="2026-06-16", cutoff="10:00", channel="github",
                 is_trading_day=True, now=_ct(10, 30))
    assert r.alert is True


def test_heartbeat_no_alert_before_cutoff():
    r = HB.check(last_sent_date="2026-06-16", cutoff="10:00", channel="github",
                 is_trading_day=True, now=_ct(9, 30))
    assert r.alert is False


def test_heartbeat_no_alert_when_sent_today():
    r = HB.check(last_sent_date="2026-06-17", cutoff="10:00", channel="github",
                 is_trading_day=True, now=_ct(11, 0))
    assert r.alert is False


def test_heartbeat_no_alert_on_non_trading_day():
    r = HB.check(last_sent_date="2026-06-12", cutoff="10:00", channel="github",
                 is_trading_day=False, now=_ct(11, 0))
    assert r.alert is False


def test_telegram_send_unconfigured_returns_false(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert HB.send_telegram("hi") is False


def test_telegram_send_configured_calls_sender(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    calls = []
    assert HB.send_telegram("hi", sender=lambda tok, cid, msg: calls.append((tok, cid, msg)))
    assert calls == [("t", "c", "hi")]
