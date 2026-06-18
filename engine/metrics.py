"""Canonical metric registry — the single source of truth for metric keys.

State, diff, the Top Story engine, and the price layer all key off the same
twelve metrics in the execution-guide Part 4.1 schema. Defining them once here
keeps those modules from drifting (DRY). Each metric declares:

  - key:           the JSON key used in last_run.json (Part 4.1)
  - label:         human-readable name
  - change_unit:   "pct" for everything except yields, which carry "bps"
                   (spec §5.5; Part 4.1: yields use change_bps, not change_pct)
  - history_source: the morning-primary source whose history seeds this metric
                   ("fred" for Treasury yields, "yfinance" for the rest, spec §5.5).
                   Mixing bases (yfinance ^TNX history under a FRED DGS10 print)
                   introduces a basis mismatch, so history must track the daily
                   value's source.

The actual symbol/series mapping (^GSPC, DGS10, etc.) lives with the price layer
in Phase 5; this module is source-agnostic so it can be imported without any
network dependency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    change_unit: str          # "pct" | "bps"
    history_source: str       # "yfinance" | "fred"


# Order matches the Part 4.1 schema for readable, diffable state files.
METRICS: tuple[Metric, ...] = (
    Metric("sp500", "S&P 500", "pct", "yfinance"),
    Metric("nasdaq", "Nasdaq Composite", "pct", "yfinance"),
    Metric("dow", "Dow Jones", "pct", "yfinance"),
    Metric("russell", "Russell 2000", "pct", "yfinance"),
    Metric("vix", "VIX", "pct", "yfinance"),
    Metric("wti", "WTI crude", "pct", "yfinance"),
    Metric("gold", "Gold", "pct", "yfinance"),
    Metric("dxy", "US Dollar Index", "pct", "yfinance"),
    Metric("ust10y", "10-year Treasury", "bps", "fred"),
    Metric("ust2y", "2-year Treasury", "bps", "fred"),
    Metric("btc", "Bitcoin", "pct", "yfinance"),
    Metric("eth", "Ethereum", "pct", "yfinance"),
)

METRIC_KEYS: tuple[str, ...] = tuple(m.key for m in METRICS)
METRICS_BY_KEY: dict[str, Metric] = {m.key: m for m in METRICS}

# Yields carry change_bps; everything else carries change_pct (Part 4.1).
YIELD_KEYS: frozenset[str] = frozenset(m.key for m in METRICS if m.change_unit == "bps")


def is_yield(key: str) -> bool:
    return key in YIELD_KEYS
