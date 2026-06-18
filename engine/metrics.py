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
    # True for rate/percent-LEVEL metrics whose trailing change is a basis-point
    # delta of the level (yields, the policy rate, inflation rates, credit spread),
    # not a percentage change of a price. Defaults from change_unit == "bps".
    rate_like: bool = False
    # Whether the metric is part of the core data set the health check requires.
    # The macro additions (copper, inflation, policy rate, credit spread) are all
    # OPTIONAL: they never trip the degraded banner or the hard floor (spec §7.5).
    optional: bool = False
    # Value display formatter hint: "index" (no decimals), "price" (2 dp), or
    # "rate" (2 dp + % suffix). Drives _fmt_value across the render layer.
    display: str = "price"
    # True for monthly/administered series (CPI, PCE, the policy rate) whose value
    # updates roughly once a month or only at a scheduled meeting. A session/week
    # change is meaningless for these (it is almost always zero), so they are shown
    # as a current-level "macro backdrop" reading, NOT in the session/week/month
    # change table. They stay OPTIONAL and never trip the banner.
    monthly: bool = False


# Order matches the Part 4.1 schema for readable, diffable state files. The first
# twelve are the original core metrics; the macro additions follow (all optional).
METRICS: tuple[Metric, ...] = (
    Metric("sp500", "S&P 500", "pct", "yfinance", display="index"),
    Metric("nasdaq", "Nasdaq Composite", "pct", "yfinance", display="index"),
    Metric("dow", "Dow Jones", "pct", "yfinance", display="index"),
    Metric("russell", "Russell 2000", "pct", "yfinance", display="index"),
    Metric("vix", "VIX", "pct", "yfinance", display="price"),
    Metric("wti", "WTI crude", "pct", "yfinance", display="price"),
    Metric("gold", "Gold", "pct", "yfinance", display="index"),
    Metric("dxy", "US Dollar Index", "pct", "yfinance", display="price"),
    Metric("ust10y", "10-year Treasury", "bps", "fred", rate_like=True, display="rate"),
    Metric("ust2y", "2-year Treasury", "bps", "fred", rate_like=True, display="rate"),
    Metric("btc", "Bitcoin", "pct", "yfinance", display="index"),
    Metric("eth", "Ethereum", "pct", "yfinance", display="index"),
    # --- Macro additions (all optional, free; spec accuracy rules unchanged) --- #
    Metric("copper", "Copper", "pct", "yfinance", display="price", optional=True),
    Metric("cpi_yoy", "CPI inflation (YoY)", "bps", "fred", rate_like=True,
           optional=True, display="rate", monthly=True),
    Metric("pce_yoy", "PCE inflation (YoY)", "bps", "fred", rate_like=True,
           optional=True, display="rate", monthly=True),
    Metric("fed_funds", "Fed funds rate", "bps", "fred", rate_like=True,
           optional=True, display="rate", monthly=True),
    Metric("hy_spread", "High-yield credit spread", "bps", "fred", rate_like=True,
           optional=True, display="rate"),
)

METRIC_KEYS: tuple[str, ...] = tuple(m.key for m in METRICS)
METRICS_BY_KEY: dict[str, Metric] = {m.key: m for m in METRICS}

# Yields carry change_bps; everything else carries change_pct (Part 4.1). The
# rate-like macro metrics also carry change_bps (a delta of a percent level).
YIELD_KEYS: frozenset[str] = frozenset(m.key for m in METRICS if m.change_unit == "bps")
RATE_LIKE_KEYS: frozenset[str] = frozenset(m.key for m in METRICS if m.rate_like)
OPTIONAL_KEYS: frozenset[str] = frozenset(m.key for m in METRICS if m.optional)
# Monthly/administered series shown as a current-level backdrop, not a change row.
MONTHLY_KEYS: frozenset[str] = frozenset(m.key for m in METRICS if m.monthly)


def is_yield(key: str) -> bool:
    """Trailing change is a basis-point delta of a percent level, not a price %.

    Originally only the two Treasury yields; now also the policy rate, the two
    inflation rates, and the credit spread, which are all percent-level series
    whose week/month move reads naturally in basis points.
    """
    return key in RATE_LIKE_KEYS


def is_optional(key: str) -> bool:
    """Optional metric: never enters the core health check (spec §7.5)."""
    return key in OPTIONAL_KEYS


def is_monthly(key: str) -> bool:
    """Monthly/administered series: shown as a current-level backdrop reading,
    not in the session/week/month change table (a daily delta is meaningless)."""
    return key in MONTHLY_KEYS
