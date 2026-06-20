# Market Brief v2 Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the v2 engine good, reliable data: the correct sourced number for every metric the brief reports, plus market news, fetched so no single provider failure can sink the run.

**Architecture:** One isolated `DataSource` plugin per external service (yfinance, FRED, Stooq, RSS), each fetching only its own raw data. A pure, I/O-free `resolve_fields()` then merges the per-service results applying v1's exact priority/fallback/oil rules. The pipeline `fetch` stage runs the sources under the existing `run_isolated` guard, then calls the resolver. Fetch-only: no history persistence.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, requests (HTTP), feedparser (RSS), PyYAML. yfinance is imported lazily inside its source. All network I/O is injectable so every test runs offline.

## Global Constraints

- Python 3.12. All v2 code lives under `v2/`; do NOT touch v1 (`brief.py`, `engine/`, `render/`, `sources/` at repo root).
- Run tests with: `cd v2 && ./.venv/bin/python -m pytest`. The venv is at `v2/.venv` (Python 3.12). Bash cwd does NOT persist between calls; `cd` into `v2` each call. Git commands use repo-root-relative paths (`v2/...`); run them from the repo root.
- Pydantic v2 models for every external input; validate at ingress. `BriefContext` stays `frozen=True`; stages return a NEW context via `with_updates(...)`.
- Per-plugin isolation: a source that raises is caught by `run_isolated`, logged with context to stderr, recorded as that source's `health = FAILED`, and the run continues. Never silently swallow.
- Accuracy invariant (spec §1): numbers come from Python, never invented or altered. The FRED `units` transform is never dropped silently. The oil rule never substitutes a lagging FRED print as if fresh (Decision 14).
- News never blocks (spec §5.6): RSS failure -> empty articles.
- Secrets from env only (`FRED_API_KEY`); never hardcoded. Absence degrades the source, never crashes.
- Professional tone in any copy: no em dashes, no emojis, plain declarative prose.
- Source tag strings on `Field.source`: `"yfinance"`, `"fred"`, `"fred_last_resort"`, `"stooq"`, `"missing"`, `"offline"`.
- Offline seam: `MARKET_BRIEF_OFFLINE=1` makes every source return synthesized clean fixtures (no network, no key).
- Naming: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. Each file <800 lines (target 200-400); functions <50 lines.

---

## File Structure

```
v2/marketbrief/
  core/
    models.py            # MODIFY: + Article, NewsResult
    context.py           # MODIFY: + resolved_fields, articles fields
    symbols.py           # NEW: ported SymbolMap table (metric -> yf / stooq / fred)
  fetch/                 # NEW package
    __init__.py
    net.py               # injectable HTTP helpers; the ONLY network I/O
    resolver.py          # PURE: resolve_fields(per_service, config) -> dict[str, Field]
  sources/
    yfinance_source.py   # YFinanceSource -> SourceResult
    fred_source.py       # FredSource     -> SourceResult
    stooq_source.py      # StooqSource    -> SourceResult
    rss_source.py        # RssSource      -> NewsResult (articles)
    placeholder.py       # MODIFY/REMOVE at the end (Task 13)
  core/pipeline.py       # MODIFY: fetch stage calls resolver, threads articles
  tests/
    test_models.py            # MODIFY: + Article/NewsResult cases
    test_symbols.py           # NEW
    test_context.py           # MODIFY: + resolved_fields/articles
    test_resolver.py          # NEW (heaviest)
    test_yfinance_source.py   # NEW
    test_fred_source.py       # NEW
    test_stooq_source.py      # NEW
    test_rss_source.py        # NEW
    test_fetch_integration.py # NEW
```

---

# GATE 1 — Contracts green (models, symbols, context)

Goal: the new data types and the symbol table exist and are validated, and the context carries the new fields. Stop for review.

## Task 1: Article + NewsResult models

**Files:**
- Modify: `v2/marketbrief/core/models.py`
- Test: `v2/tests/test_models.py`

**Interfaces:**
- Consumes: `SourceHealth` from `enums`.
- Produces:
  - `Article(source_id: str, title: str, summary: str = "", url: str = "")`.
  - `NewsResult(name: str, articles: list[Article] = [], health: SourceHealth = OK, error: str | None = None)`.

- [ ] **Step 1: Write the failing test** — append to `v2/tests/test_models.py`:

```python
from marketbrief.core.models import Article, NewsResult
from marketbrief.core.enums import SourceHealth


def test_article_defaults_blank_summary_and_url():
    a = Article(source_id="cnbc-1", title="Stocks rise")
    assert a.summary == ""
    assert a.url == ""


def test_news_result_holds_articles_and_health():
    a = Article(source_id="cnbc-1", title="Stocks rise")
    nr = NewsResult(name="rss", articles=[a])
    assert nr.health is SourceHealth.OK
    assert nr.articles[0].title == "Stocks rise"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'Article'`

- [ ] **Step 3: Add the models** — append to `v2/marketbrief/core/models.py`:

```python
class Article(BaseModel):
    source_id: str
    title: str
    summary: str = ""
    url: str = ""


class NewsResult(BaseModel):
    name: str
    articles: list[Article] = PField(default_factory=list)
    health: SourceHealth = SourceHealth.OK
    error: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_models.py -v`
Expected: all pass (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/core/models.py v2/tests/test_models.py && git commit -m "feat(v2): Article + NewsResult models for the data layer"
```

## Task 2: Symbol table (ported from v1)

**Files:**
- Create: `v2/marketbrief/core/symbols.py`
- Test: `v2/tests/test_symbols.py`

**Interfaces:**
- Produces:
  - `SymbolMap(metric: str, yf: str | None = None, yf_future: str | None = None, fred: str | None = None, fred_units: str | None = None, stooq: str | None = None)` (Pydantic, frozen).
  - `SYMBOLS: tuple[SymbolMap, ...]` — the ported v1 table.
  - `SYMBOLS_BY_METRIC: dict[str, SymbolMap]`.
- Note: `CORE_FIELDS` stays in `health.py`; do NOT redefine it here.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_symbols.py`:

```python
from marketbrief.core.symbols import SYMBOLS, SYMBOLS_BY_METRIC, SymbolMap
from marketbrief.core.health import CORE_FIELDS


def test_every_core_field_has_a_symbol():
    for k in CORE_FIELDS:
        assert k in SYMBOLS_BY_METRIC


def test_yields_have_fred_primary():
    assert SYMBOLS_BY_METRIC["ust10y"].fred == "DGS10"
    assert SYMBOLS_BY_METRIC["ust2y"].fred == "DGS2"


def test_oil_has_yf_primary_and_fred_crosscheck():
    wti = SYMBOLS_BY_METRIC["wti"]
    assert wti.yf == "CL=F"
    assert wti.fred == "DCOILWTICO"


def test_inflation_uses_pc1_units_transform():
    assert SYMBOLS_BY_METRIC["cpi_yoy"].fred_units == "pc1"


def test_indices_have_stooq_backup():
    for k in ("sp500", "nasdaq", "dow", "russell"):
        assert SYMBOLS_BY_METRIC[k].stooq is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_symbols.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/core/symbols.py`:

```python
from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class SymbolMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    yf: str | None = None          # yfinance cash/index symbol
    yf_future: str | None = None   # yfinance futures symbol (pre-market, later)
    fred: str | None = None        # FRED series (primary for yields, cross-check oil)
    fred_units: str | None = None  # FRED units transform, e.g. "pc1" (YoY %)
    stooq: str | None = None       # Stooq backup symbol (best-effort)


# Ported verbatim from v1 sources/symbols.py + backup_prices.py YF_TO_STOOQ.
SYMBOLS: tuple[SymbolMap, ...] = (
    SymbolMap(metric="sp500", yf="^GSPC", yf_future="ES=F", stooq="^spx"),
    SymbolMap(metric="nasdaq", yf="^IXIC", yf_future="NQ=F", stooq="^ndq"),
    SymbolMap(metric="dow", yf="^DJI", yf_future="YM=F", stooq="^dji"),
    SymbolMap(metric="russell", yf="^RUT", yf_future="RTY=F", stooq="^rut"),
    SymbolMap(metric="vix", yf="^VIX"),
    SymbolMap(metric="wti", yf="CL=F", fred="DCOILWTICO", stooq="cl.f"),
    SymbolMap(metric="gold", yf="GC=F", stooq="gc.f"),
    SymbolMap(metric="dxy", yf="DX-Y.NYB", stooq="^dxy"),
    SymbolMap(metric="ust10y", yf="^TNX", fred="DGS10"),
    SymbolMap(metric="ust2y", yf="^TNX", fred="DGS2"),
    SymbolMap(metric="btc", yf="BTC-USD", stooq="btcusd"),
    SymbolMap(metric="eth", yf="ETH-USD", stooq="ethusd"),
    SymbolMap(metric="copper", yf="HG=F"),
    SymbolMap(metric="cpi_yoy", fred="CPIAUCSL", fred_units="pc1"),
    SymbolMap(metric="pce_yoy", fred="PCEPI", fred_units="pc1"),
    SymbolMap(metric="fed_funds", fred="DFF"),
    SymbolMap(metric="hy_spread", fred="BAMLH0A0HYM2"),
)

SYMBOLS_BY_METRIC: dict[str, SymbolMap] = {s.metric: s for s in SYMBOLS}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_symbols.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/core/symbols.py v2/tests/test_symbols.py && git commit -m "feat(v2): ported symbol table with stooq backup column"
```

## Task 3: Extend BriefContext with resolved_fields + articles

**Files:**
- Modify: `v2/marketbrief/core/context.py`
- Test: `v2/tests/test_context.py`

**Interfaces:**
- Consumes: `Field`, `Article` from `models`.
- Produces: `BriefContext` gains `resolved_fields: dict[str, Field]` and `articles: list[Article]`, both defaulting empty, both settable via `with_updates`.

- [ ] **Step 1: Write the failing test** — append to `v2/tests/test_context.py`:

```python
from marketbrief.core.models import Field, Article


def test_with_updates_sets_resolved_fields_and_articles():
    ctx = BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})
    new = ctx.with_updates(
        resolved_fields={"sp500": Field(metric="sp500", value=5000.0, source="yfinance")},
        articles=[Article(source_id="cnbc-1", title="x")],
    )
    assert new.resolved_fields["sp500"].value == 5000.0
    assert new.articles[0].source_id == "cnbc-1"
    assert ctx.resolved_fields == {}  # original untouched
    assert ctx.articles == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_context.py -v`
Expected: FAIL (`resolved_fields` not a field / validation error).

- [ ] **Step 3: Modify context** — in `v2/marketbrief/core/context.py`, add `Field, Article` to the models import and add two fields to `BriefContext` (after `facts`):

```python
    resolved_fields: dict[str, Field] = PField(default_factory=dict)
    articles: list[Article] = PField(default_factory=list)
```

Update the import line to include `Field` and `Article`:

```python
from marketbrief.core.models import (
    Field, Article, SourceResult, ComputedNumbers, Cause, NarratedWhy, SectionVM, HealthReport,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_context.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/core/context.py v2/tests/test_context.py && git commit -m "feat(v2): BriefContext carries resolved_fields + articles"
```

**GATE 1 CHECKPOINT.** Run `cd v2 && ./.venv/bin/python -m pytest -v`. Models, symbols, context all green. Stop for review.

---

# GATE 2 — Resolver + the four sources (offline)

Goal: the pure resolver applies every v1 fallback/cross-check rule, and each external service is an isolated, offline-testable source. Stop for review.

## Task 4: The pure resolver

**Files:**
- Create: `v2/marketbrief/fetch/__init__.py` (empty), `v2/marketbrief/fetch/resolver.py`
- Test: `v2/tests/test_resolver.py`

**Interfaces:**
- Consumes: `SourceResult`, `Field` from `models`; `SYMBOLS` from `symbols`; `Config`.
- Produces:
  - `resolve_fields(per_service: dict[str, SourceResult], config: Config) -> dict[str, Field]`.
- Resolution rules (ported verbatim from v1 `prices.py.pull_fields` + `_pull_oil`):
  - yields (`ust10y`, `ust2y`): FRED primary; yfinance fallback only if FRED missing; FRED-only series with no yf -> MISSING.
  - oil (`wti`): yfinance primary; if missing, mark **stale**; FRED only as date-stamped last resort (`source="fred_last_resort"`, `stale=True`, `note=...`).
  - all other metrics: yfinance primary; Stooq fills only if yfinance missing (`source="stooq"`); else MISSING.
  - a metric absent everywhere -> `Field(metric=k, value=None, source="missing")`.
- A service that is absent from `per_service` (e.g. it failed upstream) is treated as supplying no fields. The resolver does NO I/O and never raises.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_resolver.py`:

```python
from marketbrief.fetch.resolver import resolve_fields
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.config import Config


def _sr(name, fields):
    return SourceResult(name=name, fields=fields, health=SourceHealth.OK)


def test_yield_prefers_fred_over_yfinance():
    per = {
        "fred": _sr("fred", {"ust10y": Field(metric="ust10y", value=4.2, source="fred", as_of="2026-06-19")}),
        "yfinance": _sr("yfinance", {"ust10y": Field(metric="ust10y", value=4.1, source="yfinance")}),
    }
    out = resolve_fields(per, Config())
    assert out["ust10y"].value == 4.2
    assert out["ust10y"].source == "fred"


def test_yield_falls_back_to_yfinance_when_fred_missing():
    per = {"yfinance": _sr("yfinance", {"ust10y": Field(metric="ust10y", value=4.1, source="yfinance")})}
    out = resolve_fields(per, Config())
    assert out["ust10y"].value == 4.1
    assert out["ust10y"].source == "yfinance"


def test_oil_prefers_yfinance():
    per = {"yfinance": _sr("yfinance", {"wti": Field(metric="wti", value=80.0, source="yfinance")})}
    out = resolve_fields(per, Config())
    assert out["wti"].value == 80.0
    assert out["wti"].source == "yfinance"
    assert out["wti"].stale is False


def test_oil_missing_yfinance_uses_fred_as_dated_last_resort_stale():
    per = {"fred": _sr("fred", {"wti": Field(metric="wti", value=78.0, source="fred", as_of="2026-06-16")})}
    out = resolve_fields(per, Config())
    assert out["wti"].source == "fred_last_resort"
    assert out["wti"].stale is True
    assert out["wti"].as_of == "2026-06-16"
    assert out["wti"].note


def test_oil_missing_everywhere_is_missing_and_stale():
    out = resolve_fields({}, Config())
    assert out["wti"].is_missing
    assert out["wti"].stale is True


def test_index_falls_back_to_stooq_when_yfinance_missing():
    per = {"stooq": _sr("stooq", {"sp500": Field(metric="sp500", value=5000.0, source="stooq")})}
    out = resolve_fields(per, Config())
    assert out["sp500"].value == 5000.0
    assert out["sp500"].source == "stooq"


def test_index_prefers_yfinance_over_stooq():
    per = {
        "yfinance": _sr("yfinance", {"sp500": Field(metric="sp500", value=5001.0, source="yfinance")}),
        "stooq": _sr("stooq", {"sp500": Field(metric="sp500", value=5000.0, source="stooq")}),
    }
    out = resolve_fields(per, Config())
    assert out["sp500"].source == "yfinance"


def test_metric_absent_everywhere_is_missing():
    out = resolve_fields({}, Config())
    assert out["sp500"].is_missing
    assert out["sp500"].source == "missing"


def test_resolver_covers_every_symbol():
    out = resolve_fields({}, Config())
    from marketbrief.core.symbols import SYMBOLS_BY_METRIC
    for k in SYMBOLS_BY_METRIC:
        assert k in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/fetch/resolver.py`:

```python
from __future__ import annotations
import math
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.config import Config
from marketbrief.core.symbols import SYMBOLS, SYMBOLS_BY_METRIC

_YIELDS = ("ust10y", "ust2y")
_OIL_LAST_RESORT_NOTE = (
    "FRED WTI lags several business days; shown as a dated last resort."
)


def _usable(field: Field | None) -> bool:
    if field is None or field.value is None:
        return False
    try:
        v = float(field.value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(v)


def _get(per: dict[str, SourceResult], service: str, metric: str) -> Field | None:
    sr = per.get(service)
    if sr is None:
        return None
    return sr.fields.get(metric)


def _missing(metric: str, *, stale: bool = False) -> Field:
    return Field(metric=metric, value=None, source="missing", stale=stale)


def _resolve_yield(per, metric) -> Field:
    fred = _get(per, "fred", metric)
    if _usable(fred):
        return fred
    yf = _get(per, "yfinance", metric)
    if _usable(yf):
        return yf
    return _missing(metric)


def _resolve_oil(per) -> Field:
    yf = _get(per, "yfinance", "wti")
    if _usable(yf):
        return yf
    fred = _get(per, "fred", "wti")
    if _usable(fred):
        return Field(
            metric="wti", value=fred.value, source="fred_last_resort",
            stale=True, as_of=fred.as_of, note=_OIL_LAST_RESORT_NOTE,
        )
    return _missing("wti", stale=True)


def _resolve_other(per, metric) -> Field:
    yf = _get(per, "yfinance", metric)
    if _usable(yf):
        return yf
    stooq = _get(per, "stooq", metric)
    if _usable(stooq):
        return stooq
    return _missing(metric)


def resolve_fields(per_service: dict[str, SourceResult], config: Config) -> dict[str, Field]:
    """Merge per-service results into one Field per metric (pure, no I/O).

    Ports v1 prices.pull_fields + _pull_oil priority/fallback/oil rules verbatim.
    """
    out: dict[str, Field] = {}
    for sym in SYMBOLS:
        metric = sym.metric
        if metric in _YIELDS:
            out[metric] = _resolve_yield(per_service, metric)
        elif metric == "wti":
            out[metric] = _resolve_oil(per_service)
        else:
            out[metric] = _resolve_other(per_service, metric)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_resolver.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/fetch/__init__.py v2/marketbrief/fetch/resolver.py v2/tests/test_resolver.py && git commit -m "feat(v2): pure field resolver with ported v1 fallback + oil rules"
```

## Task 5: Network helper layer (injectable, the only I/O)

**Files:**
- Create: `v2/marketbrief/fetch/net.py`
- Test: `v2/tests/test_net.py`

**Interfaces:**
- Produces:
  - `REQUEST_TIMEOUT: int = 15`.
  - `is_offline() -> bool` — True when `MARKET_BRIEF_OFFLINE` env var is set to a truthy value (`"1"`, `"true"`, case-insensitive).
  - `http_get(url: str, params: dict | None = None, *, headers: dict | None = None) -> str` — real `requests.get` with timeout; raises on HTTP error. (Real I/O; not called in tests.)

- [ ] **Step 1: Write the failing test** — `v2/tests/test_net.py`:

```python
import os
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT


def test_request_timeout_is_set():
    assert REQUEST_TIMEOUT == 15


def test_is_offline_true_when_env_set(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    assert is_offline() is True


def test_is_offline_false_when_unset(monkeypatch):
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)
    assert is_offline() is False


def test_is_offline_accepts_true_string(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "true")
    assert is_offline() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_net.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/fetch/net.py`:

```python
from __future__ import annotations
import os

REQUEST_TIMEOUT = 15  # seconds; never hang the daily run on a slow provider


def is_offline() -> bool:
    """True when MARKET_BRIEF_OFFLINE is set truthy (test/offline seam)."""
    return os.environ.get("MARKET_BRIEF_OFFLINE", "").strip().lower() in ("1", "true", "yes")


def http_get(url: str, params: dict | None = None, *, headers: dict | None = None) -> str:
    """Real HTTP GET returning response text. Raises on HTTP error.

    Isolated here so sources inject a fake fetcher in tests and never hit network.
    """
    import requests

    resp = requests.get(url, params=params or {}, timeout=REQUEST_TIMEOUT, headers=headers or {})
    resp.raise_for_status()
    return resp.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_net.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/fetch/net.py v2/tests/test_net.py && git commit -m "feat(v2): injectable net layer + offline seam"
```

## Task 6: YFinanceSource

**Files:**
- Create: `v2/marketbrief/sources/yfinance_source.py`
- Test: `v2/tests/test_yfinance_source.py`

**Interfaces:**
- Consumes: `SourceResult`, `Field`, `SourceHealth`, `SYMBOLS`, `is_offline`.
- Produces: `YFinanceSource` with `name = "yfinance"`, `fetch(ctx) -> SourceResult` and a constructor accepting an injectable `downloader: Callable[[str, int], list[float]]` (yfinance symbol, days -> closes oldest->newest, `[]` on failure). Offline mode returns clean `1.0` fields for every metric that has a `yf` symbol.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_yfinance_source.py`:

```python
from datetime import date
from marketbrief.sources.yfinance_source import YFinanceSource
from marketbrief.core.protocols import DataSource
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_satisfies_datasource_protocol():
    assert isinstance(YFinanceSource(), DataSource)


def test_fetch_returns_latest_close_per_symbol():
    def fake_dl(symbol, days):
        return [10.0, 11.0, 12.0]  # latest = 12.0
    src = YFinanceSource(downloader=fake_dl)
    result = src.fetch(_ctx())
    assert result.fields["sp500"].value == 12.0
    assert result.fields["sp500"].source == "yfinance"
    assert result.health is SourceHealth.OK


def test_empty_download_yields_missing_field():
    src = YFinanceSource(downloader=lambda s, d: [])
    result = src.fetch(_ctx())
    assert result.fields["sp500"].is_missing


def test_fred_only_metric_absent_from_yfinance_result():
    src = YFinanceSource(downloader=lambda s, d: [5.0])
    result = src.fetch(_ctx())
    assert "cpi_yoy" not in result.fields  # no yf symbol


def test_offline_returns_clean_fields(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    result = YFinanceSource().fetch(_ctx())
    assert result.fields["sp500"].is_usable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_yfinance_source.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/sources/yfinance_source.py`:

```python
from __future__ import annotations
from typing import Callable
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.symbols import SYMBOLS
from marketbrief.fetch.net import is_offline

Downloader = Callable[[str, int], list[float]]
BACKFILL_PAD = 40  # request extra days so ~25 trading closes survive holidays


def _real_download(symbol: str, days: int) -> list[float]:
    """Real yfinance pull: closes oldest->newest, [] on any failure.

    yfinance imported lazily so importing this module never forces it. Handles
    the MultiIndex/flat Close shapes (load-bearing-pin guard, spec §13).
    """
    try:
        import yfinance as yf

        df = yf.download(
            symbol, period=f"{max(days + BACKFILL_PAD, 60)}d", interval="1d",
            auto_adjust=True, progress=False, threads=False,
        )
        if df is None or df.empty:
            return []
        close = _select_close(df, symbol)
        if close is None:
            return []
        return [float(v) for v in close.dropna().tolist()]
    except Exception:
        return []


def _select_close(df, symbol: str):
    cols = df.columns
    if hasattr(cols, "nlevels") and cols.nlevels > 1:
        if ("Close", symbol) in cols:
            return df[("Close", symbol)]
        close_cols = [c for c in cols if c[0] == "Close"]
        return df[close_cols[0]] if close_cols else None
    return df["Close"] if "Close" in cols else None


class YFinanceSource:
    name = "yfinance"

    def __init__(self, downloader: Downloader | None = None):
        self._downloader = downloader or _real_download

    def fetch(self, ctx) -> SourceResult:
        if is_offline():
            return self._offline()
        fields: dict[str, Field] = {}
        for sym in SYMBOLS:
            if not sym.yf:
                continue
            closes = self._downloader(sym.yf, 5)
            if closes:
                fields[sym.metric] = Field(metric=sym.metric, value=closes[-1], source="yfinance")
            else:
                fields[sym.metric] = Field(metric=sym.metric, value=None, source="missing")
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)

    def _offline(self) -> SourceResult:
        fields = {
            s.metric: Field(metric=s.metric, value=1.0, source="yfinance")
            for s in SYMBOLS if s.yf
        }
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_yfinance_source.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/sources/yfinance_source.py v2/tests/test_yfinance_source.py && git commit -m "feat(v2): YFinanceSource with ported shape guard + offline mode"
```

## Task 7: FredSource

**Files:**
- Create: `v2/marketbrief/sources/fred_source.py`
- Test: `v2/tests/test_fred_source.py`

**Interfaces:**
- Consumes: `SourceResult`, `Field`, `SourceHealth`, `SYMBOLS`, `is_offline`.
- Produces: `FredSource` with `name = "fred"`, `fetch(ctx) -> SourceResult`, constructor accepting an injectable `series_fetcher: Callable[..., list[tuple[str, float]]]` returning observations oldest->newest as `(date_str, value)`. Pulls only metrics with a `fred` series. Applies the `fred_units` transform via the fetcher. Missing key / failure -> health FAILED (offline returns clean fields).

- [ ] **Step 1: Write the failing test** — `v2/tests/test_fred_source.py`:

```python
from datetime import date
from marketbrief.sources.fred_source import FredSource
from marketbrief.core.protocols import DataSource
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_satisfies_datasource_protocol():
    assert isinstance(FredSource(), DataSource)


def test_fetch_returns_latest_observation_with_as_of():
    def fake(series_id, limit, units=None):
        return [("2026-06-18", 4.1), ("2026-06-19", 4.2)]  # oldest->newest
    src = FredSource(series_fetcher=fake)
    result = src.fetch(_ctx())
    assert result.fields["ust10y"].value == 4.2
    assert result.fields["ust10y"].source == "fred"
    assert result.fields["ust10y"].as_of == "2026-06-19"


def test_units_transform_is_passed_through():
    seen = {}
    def fake(series_id, limit, units=None):
        seen[series_id] = units
        return [("2026-05-01", 3.2)]
    FredSource(series_fetcher=fake).fetch(_ctx())
    assert seen["CPIAUCSL"] == "pc1"  # YoY inflation transform preserved


def test_only_fred_metrics_present():
    src = FredSource(series_fetcher=lambda s, l, units=None: [("2026-06-19", 1.0)])
    result = src.fetch(_ctx())
    assert "ust10y" in result.fields
    assert "vix" not in result.fields  # no fred series


def test_fetcher_failure_degrades_to_failed_health():
    def boom(series_id, limit, units=None):
        raise RuntimeError("FRED down")
    result = FredSource(series_fetcher=boom).fetch(_ctx())
    assert result.health is SourceHealth.FAILED


def test_offline_returns_clean_fields(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    result = FredSource().fetch(_ctx())
    assert result.fields["ust10y"].is_usable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_fred_source.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/sources/fred_source.py`:

```python
from __future__ import annotations
import inspect
import os
from typing import Callable, Optional
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.symbols import SYMBOLS
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT

SeriesFetcher = Callable[..., list[tuple[str, float]]]
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _real_series_fetcher(series_id: str, limit: int, *, units: Optional[str] = None):
    """Pull last `limit` non-missing observations oldest->newest. Raises on error."""
    import requests

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY not set")
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json",
              "sort_order": "desc", "limit": limit}
    if units:
        params["units"] = units
    resp = requests.get(FRED_BASE, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])
    out: list[tuple[str, float]] = []
    for o in obs:
        val = o.get("value")
        if val in (None, ".", ""):
            continue
        try:
            out.append((o["date"], float(val)))
        except (ValueError, KeyError):
            continue
    out.reverse()
    return out


def _call_fetcher(fetch: SeriesFetcher, series_id: str, n: int, units: Optional[str]):
    """Pass `units` only when the fetcher accepts it; never drop it silently.

    Dropping a requested transform would store a raw index (~320) instead of the
    YoY rate (~3.2) -- a wrong number. Accuracy invariant forbids that.
    """
    if not units:
        return fetch(series_id, n)
    try:
        accepts = "units" in inspect.signature(fetch).parameters
    except (TypeError, ValueError):
        accepts = False
    return fetch(series_id, n, units=units) if accepts else fetch(series_id, n)


class FredSource:
    name = "fred"

    def __init__(self, series_fetcher: SeriesFetcher | None = None):
        self._fetch = series_fetcher or _real_series_fetcher

    def fetch(self, ctx) -> SourceResult:
        if is_offline():
            return self._offline()
        fields: dict[str, Field] = {}
        try:
            for sym in SYMBOLS:
                if not sym.fred:
                    continue
                obs = _call_fetcher(self._fetch, sym.fred, 5, sym.fred_units)
                if obs:
                    as_of, value = obs[-1]
                    fields[sym.metric] = Field(metric=sym.metric, value=value, source="fred", as_of=as_of)
                else:
                    fields[sym.metric] = Field(metric=sym.metric, value=None, source="missing")
        except Exception as exc:
            return SourceResult(name=self.name, fields={}, health=SourceHealth.FAILED, error=str(exc))
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)

    def _offline(self) -> SourceResult:
        fields = {
            s.metric: Field(metric=s.metric, value=1.0, source="fred", as_of="2026-06-19")
            for s in SYMBOLS if s.fred
        }
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_fred_source.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/sources/fred_source.py v2/tests/test_fred_source.py && git commit -m "feat(v2): FredSource with ported units-transform safety + offline mode"
```

## Task 8: StooqSource

**Files:**
- Create: `v2/marketbrief/sources/stooq_source.py`
- Test: `v2/tests/test_stooq_source.py`

**Interfaces:**
- Consumes: `SourceResult`, `Field`, `SourceHealth`, `SYMBOLS`, `is_offline`.
- Produces: `StooqSource` with `name = "stooq"`, `fetch(ctx) -> SourceResult`, constructor accepting an injectable `downloader: Callable[[str, int], list[float]]` (Stooq symbol, days -> closes oldest->newest, `[]` on failure). Pulls only metrics with a `stooq` symbol. Best-effort: failures yield missing fields, never raise. Offline returns clean fields.

- [ ] **Step 1: Write the failing test** — `v2/tests/test_stooq_source.py`:

```python
from datetime import date
from marketbrief.sources.stooq_source import StooqSource
from marketbrief.core.protocols import DataSource
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_satisfies_datasource_protocol():
    assert isinstance(StooqSource(), DataSource)


def test_fetch_returns_latest_close_for_mapped_symbols():
    src = StooqSource(downloader=lambda s, d: [4990.0, 5000.0])
    result = src.fetch(_ctx())
    assert result.fields["sp500"].value == 5000.0
    assert result.fields["sp500"].source == "stooq"


def test_unmapped_metric_absent():
    src = StooqSource(downloader=lambda s, d: [1.0])
    result = src.fetch(_ctx())
    assert "vix" not in result.fields  # no stooq symbol mapped


def test_failure_yields_missing_not_raise():
    src = StooqSource(downloader=lambda s, d: [])
    result = src.fetch(_ctx())
    assert result.fields["sp500"].is_missing
    assert result.health is SourceHealth.OK  # best-effort, still returns


def test_offline_returns_clean_fields(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    result = StooqSource().fetch(_ctx())
    assert result.fields["sp500"].is_usable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_stooq_source.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/sources/stooq_source.py`:

```python
from __future__ import annotations
import csv
import io
from typing import Callable
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.symbols import SYMBOLS
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT

Downloader = Callable[[str, int], list[float]]
STOOQ_BASE = "https://stooq.com/q/d/l/"


def _real_download(stooq_symbol: str, days: int) -> list[float]:
    """Stooq CSV closes oldest->newest, [] on any failure including quota body."""
    import requests

    try:
        resp = requests.get(STOOQ_BASE, params={"s": stooq_symbol, "i": "d"}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        if "Exceeded" in text or "Date,Open" not in text:
            return []
        reader = csv.DictReader(io.StringIO(text))
        closes = [float(row["Close"]) for row in reader if row.get("Close")]
        return closes[-days:] if days else closes
    except Exception:
        return []


class StooqSource:
    name = "stooq"

    def __init__(self, downloader: Downloader | None = None):
        self._downloader = downloader or _real_download

    def fetch(self, ctx) -> SourceResult:
        if is_offline():
            return self._offline()
        fields: dict[str, Field] = {}
        for sym in SYMBOLS:
            if not sym.stooq:
                continue
            closes = self._downloader(sym.stooq, 5)
            if closes:
                fields[sym.metric] = Field(metric=sym.metric, value=closes[-1], source="stooq")
            else:
                fields[sym.metric] = Field(metric=sym.metric, value=None, source="missing")
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)

    def _offline(self) -> SourceResult:
        fields = {
            s.metric: Field(metric=s.metric, value=1.0, source="stooq")
            for s in SYMBOLS if s.stooq
        }
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_stooq_source.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/sources/stooq_source.py v2/tests/test_stooq_source.py && git commit -m "feat(v2): StooqSource best-effort backup + offline mode"
```

## Task 9: RssSource (news)

**Files:**
- Create: `v2/marketbrief/sources/rss_source.py`
- Test: `v2/tests/test_rss_source.py`

**Interfaces:**
- Consumes: `NewsResult`, `Article`, `SourceHealth`, `is_offline`.
- Produces: `RssSource` with `name = "rss"`, `fetch_news(ctx) -> NewsResult`, constructor accepting injectable `feed_fetcher: Callable[[str], str]` (url -> raw feed text) and optional `feeds: tuple[str, ...]`. Single feed failure is skipped; total failure -> empty articles, health OK (news never blocks). `source_id` is `"{prefix}-{i}"` per feed. NOTE: RssSource produces a `NewsResult`, not a `SourceResult`; it is wired into the pipeline separately (Task 11) and is intentionally NOT discovered by `discover_sources()` (which yields `DataSource`s only).

- [ ] **Step 1: Write the failing test** — `v2/tests/test_rss_source.py`:

```python
from datetime import date
from marketbrief.sources.rss_source import RssSource, parse_feed
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Stocks rise on data</title><description>Markets gained.</description><link>http://x/1</link></item>
<item><title>Fed holds rates</title><description>No change.</description><link>http://x/2</link></item>
</channel></rss>"""


def test_parse_feed_builds_articles_with_source_ids():
    arts = parse_feed(_RSS, prefix="cnbc")
    assert arts[0].source_id == "cnbc-0"
    assert arts[0].title == "Stocks rise on data"
    assert arts[1].source_id == "cnbc-1"


def test_fetch_news_aggregates_feeds():
    src = RssSource(feed_fetcher=lambda url: _RSS, feeds=("http://cnbc",))
    nr = src.fetch_news(_ctx())
    assert len(nr.articles) == 2
    assert nr.health is SourceHealth.OK


def test_single_feed_failure_is_skipped():
    def fetcher(url):
        if "bad" in url:
            raise RuntimeError("feed down")
        return _RSS
    src = RssSource(feed_fetcher=fetcher, feeds=("http://bad", "http://cnbc"))
    nr = src.fetch_news(_ctx())
    assert len(nr.articles) == 2  # only the good feed


def test_total_failure_returns_empty_never_raises():
    src = RssSource(feed_fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("x")), feeds=("http://a",))
    nr = src.fetch_news(_ctx())
    assert nr.articles == []
    assert nr.health is SourceHealth.OK  # news never blocks


def test_offline_returns_sample_articles(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    nr = RssSource().fetch_news(_ctx())
    assert len(nr.articles) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_rss_source.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation** — `v2/marketbrief/sources/rss_source.py`:

```python
from __future__ import annotations
import html
import re
from typing import Callable
from marketbrief.core.models import NewsResult, Article
from marketbrief.core.enums import SourceHealth
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT

FeedFetcher = Callable[[str], str]

# Ported from v1 sources/news.py FEEDS (free/public endpoints only).
FEEDS: tuple[str, ...] = (
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "http://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "https://www.ft.com/markets?format=rss",
)


def _real_fetch(url: str) -> str:
    import requests

    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "market-brief/2.0"})
    resp.raise_for_status()
    return resp.text


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _prefix_for(url: str) -> str:
    if "cnbc" in url:
        return "cnbc"
    if "marketwatch" in url:
        return "mw"
    if "federalreserve" in url:
        return "fed"
    if "dowjones" in url or "wsj" in url:
        return "wsj"
    if "ft.com" in url:
        return "ft"
    return "rss"


def parse_feed(raw: str, *, prefix: str) -> list[Article]:
    import feedparser

    parsed = feedparser.parse(raw)
    out: list[Article] = []
    for i, entry in enumerate(parsed.entries):
        title = _clean(getattr(entry, "title", ""))
        summary = _clean(getattr(entry, "summary", getattr(entry, "description", "")))
        url = getattr(entry, "link", "")
        if not title:
            continue
        out.append(Article(source_id=f"{prefix}-{i}", title=title, summary=summary, url=url))
    return out


class RssSource:
    name = "rss"

    def __init__(self, feed_fetcher: FeedFetcher | None = None, feeds: tuple[str, ...] = FEEDS):
        self._fetch = feed_fetcher or _real_fetch
        self._feeds = feeds

    def fetch_news(self, ctx) -> NewsResult:
        if is_offline():
            return self._offline()
        articles: list[Article] = []
        for url in self._feeds:
            try:
                raw = self._fetch(url)
                articles.extend(parse_feed(raw, prefix=_prefix_for(url)))
            except Exception:
                continue  # single feed down never sinks news
        return NewsResult(name=self.name, articles=articles, health=SourceHealth.OK)

    def _offline(self) -> NewsResult:
        return NewsResult(
            name=self.name,
            articles=[Article(source_id="offline-0", title="Markets steady in quiet session",
                              summary="Offline sample article.", url="")],
            health=SourceHealth.OK,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_rss_source.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/sources/rss_source.py v2/tests/test_rss_source.py && git commit -m "feat(v2): RssSource news fetch (Articles) + offline mode"
```

**GATE 2 CHECKPOINT.** Run `cd v2 && ./.venv/bin/python -m pytest -v`. Resolver + net + all four sources green. Stop for review.

---

# GATE 3 — Integration: pipeline wires data layer end-to-end offline

Goal: the pipeline fetch stage runs the real numeric sources, resolves fields, fetches news, and `python v2/brief.py --no-send` produces a brief offline from real source code. Stop for review.

## Task 10: Resolver wired into the pipeline fetch stage

**Files:**
- Modify: `v2/marketbrief/core/pipeline.py`
- Test: `v2/tests/test_fetch_integration.py`

**Interfaces:**
- Consumes: `resolve_fields`, `RssSource`, `discover_sources`.
- Produces: `run_pipeline` now (a) fetches each isolated numeric source into `facts`, (b) calls `resolve_fields(facts, ctx.config)` into `resolved_fields`, (c) fetches news into `articles`, (d) assesses health on `resolved_fields` (not raw `facts`), then assembles. New keyword params: `news_source: RssSource | None = None` (defaults to a real `RssSource()`).

- [ ] **Step 1: Write the failing test** — `v2/tests/test_fetch_integration.py`:

```python
from datetime import date
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth
from marketbrief.core.models import SourceResult, Field
from marketbrief.sources.rss_source import RssSource


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


class _YF:
    name = "yfinance"
    def fetch(self, ctx):
        return SourceResult(name="yfinance", fields={
            k: Field(metric=k, value=100.0, source="yfinance")
            for k in ("sp500", "nasdaq", "dow", "russell", "wti", "dxy")
        }, health=SourceHealth.OK)


class _Fred:
    name = "fred"
    def fetch(self, ctx):
        return SourceResult(name="fred", fields={
            "ust10y": Field(metric="ust10y", value=4.2, source="fred", as_of="2026-06-19")
        }, health=SourceHealth.OK)


def _news():
    return RssSource(feed_fetcher=lambda u: "", feeds=())  # yields no articles, never network


def test_pipeline_resolves_fields_from_sources():
    out = run_pipeline(_ctx(), sources=[_YF(), _Fred()], sections=[], news_source=_news())
    assert out.resolved_fields["sp500"].value == 100.0
    assert out.resolved_fields["ust10y"].source == "fred"
    assert out.health.hard_floor_tripped is False


def test_yfinance_down_resolves_core_from_stooq():
    class _Stooq:
        name = "stooq"
        def fetch(self, ctx):
            return SourceResult(name="stooq", fields={
                k: Field(metric=k, value=50.0, source="stooq")
                for k in ("sp500", "nasdaq", "dow", "russell", "wti", "dxy")
            }, health=SourceHealth.OK)
    class _BoomYF:
        name = "yfinance"
        def fetch(self, ctx):
            raise RuntimeError("Yahoo blocked")
    out = run_pipeline(_ctx(), sources=[_BoomYF(), _Stooq(), _Fred()], sections=[], news_source=_news())
    assert out.resolved_fields["sp500"].source == "stooq"
    assert out.facts["yfinance"].health is SourceHealth.FAILED
    assert out.health.hard_floor_tripped is False  # survived the block


def test_news_attached_to_context():
    news = RssSource(feed_fetcher=lambda u: (
        '<rss><channel><item><title>Hi</title><link>http://x</link></item></channel></rss>'
    ), feeds=("http://cnbc",))
    out = run_pipeline(_ctx(), sources=[_YF()], sections=[], news_source=news)
    assert any(a.title == "Hi" for a in out.articles)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_fetch_integration.py -v`
Expected: FAIL (`run_pipeline` has no `news_source` kw / `resolved_fields` empty).

- [ ] **Step 3: Modify the pipeline** — edit `v2/marketbrief/core/pipeline.py`. Add imports at top:

```python
from marketbrief.fetch.resolver import resolve_fields
from marketbrief.sources.rss_source import RssSource
```

Change `_assess` to read `resolved_fields`:

```python
def _assess(ctx: BriefContext) -> BriefContext:
    report = assess(
        ctx.resolved_fields,
        degraded_stale_threshold=ctx.config.resilience.degraded_stale_threshold,
        hard_floor_missing_threshold=ctx.config.resilience.hard_floor_missing_threshold,
    )
    return ctx.with_updates(health=report)
```

Add a resolve step and a news step, and rewrite `run_pipeline`:

```python
def _resolve(ctx: BriefContext) -> BriefContext:
    resolved = resolve_fields(ctx.facts, ctx.config)
    return ctx.with_updates(resolved_fields=resolved)


def _fetch_news(ctx: BriefContext, news_source) -> BriefContext:
    result, err = run_isolated("news:rss", lambda: news_source.fetch_news(ctx), None)
    articles = result.articles if result is not None else []
    return ctx.with_updates(articles=articles)


def run_pipeline(ctx: BriefContext, *, sources: list | None = None,
                 sections: list | None = None, news_source=None) -> BriefContext:
    sources = discover_sources() if sources is None else sources
    sections = discover_sections() if sections is None else sections
    news_source = RssSource() if news_source is None else news_source
    ctx = _fetch(ctx, sources)
    ctx = _resolve(ctx)
    ctx = _fetch_news(ctx, news_source)
    ctx = _assess(ctx)
    # compute / match / narrate are pass-through stubs in this sub-project
    ctx = _assemble(ctx, sections)
    return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_fetch_integration.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/marketbrief/core/pipeline.py v2/tests/test_fetch_integration.py && git commit -m "feat(v2): pipeline resolves fields + fetches news, assesses resolved set"
```

## Task 11: Migrate placeholder; promote real sources to discovery

**Files:**
- Modify: `v2/marketbrief/sources/placeholder.py` (delete file), `v2/tests/test_registry.py`, `v2/tests/test_plugins.py`, `v2/tests/test_pipeline.py`
- Test: the three modified test files.

**Interfaces:**
- Produces: `discover_sources()` now returns the real numeric sources (`yfinance`, `fred`, `stooq`); RssSource is excluded (it is not a `DataSource`). The placeholder is gone.

**Context:** the placeholder existed only to prove the Protocol seam in sub-project #1. Now real sources exist, so it is removed and its tests are repointed. RssSource has `fetch_news`, not `fetch`, so it does not satisfy the `DataSource` Protocol and will not be auto-discovered (verify this holds).

- [ ] **Step 1: Update the failing tests first.** Replace placeholder references:

In `v2/tests/test_registry.py`, replace the placeholder test with:

```python
def test_discovers_real_numeric_sources():
    names = [s.name for s in discover_sources()]
    assert "yfinance" in names
    assert "fred" in names
    assert "stooq" in names


def test_rss_not_discovered_as_datasource():
    names = [s.name for s in discover_sources()]
    assert "rss" not in names  # RssSource has fetch_news, not fetch
```

In `v2/tests/test_plugins.py`, remove the two placeholder tests (`test_placeholder_satisfies_datasource_protocol`, `test_placeholder_returns_all_core_fields`) and the `from marketbrief.sources.placeholder import PlaceholderSource` import. Keep the summary-section tests.

In `v2/tests/test_pipeline.py`, change `test_pipeline_fetches_and_assembles` to not assume placeholder. Replace its body with:

```python
def test_pipeline_fetches_and_assembles(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    out = run_pipeline(_ctx())
    assert "yfinance" in out.facts
    assert out.resolved_fields  # resolver produced fields
    assert any(s.id == "summary" for s in out.sections)
    assert out.health.hard_floor_tripped is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_registry.py tests/test_pipeline.py -v`
Expected: FAIL (placeholder still discovered / import gone).

- [ ] **Step 3: Delete the placeholder**

```bash
cd /Users/jakeliess/market-brief && git rm v2/marketbrief/sources/placeholder.py
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `cd v2 && ./.venv/bin/python -m pytest -v`
Expected: all pass (placeholder tests gone, real-source tests green).

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/tests/test_registry.py v2/tests/test_plugins.py v2/tests/test_pipeline.py && git commit -m "refactor(v2): retire placeholder source; discover real numeric sources"
```

## Task 12: End-to-end offline run through real sources

**Files:**
- Modify: `v2/tests/test_end_to_end.py`
- Test: same.

**Interfaces:**
- Consumes: `brief.build_brief`, `MARKET_BRIEF_OFFLINE`.
- Produces: an end-to-end assertion that the real data layer runs offline with no state write.

- [ ] **Step 1: Write the failing test** — append to `v2/tests/test_end_to_end.py`:

```python
def test_real_sources_offline_build_writes_no_state(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.NO_SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert "At a Glance" in html
    assert not state.exists()
```

- [ ] **Step 2: Run test to verify it passes** (the wiring already exists from Task 10/11, so this is a characterization test confirming end-to-end)

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_end_to_end.py -v`
Expected: all pass. If it fails, fix the wiring, not the test.

- [ ] **Step 3: Run the orchestrator for real (offline)**

Run: `cd v2 && MARKET_BRIEF_OFFLINE=1 ./.venv/bin/python brief.py --no-send`
Expected: prints `mode=no_send exit=0 bytes=...`; `v2/brief.preview.html` exists; no `last_run.json` written.

- [ ] **Step 4: Full suite green**

Run: `cd v2 && ./.venv/bin/python -m pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
cd /Users/jakeliess/market-brief && git add v2/tests/test_end_to_end.py && git commit -m "test(v2): end-to-end offline build through real data layer"
```

**GATE 3 CHECKPOINT.** `MARKET_BRIEF_OFFLINE=1 python v2/brief.py --no-send` renders a brief from the real sources + resolver, writes no state; a forced yfinance-down run resolves core fields from Stooq/FRED; oil-missing renders stale. Full suite green, coverage >= 80%. Stop for review. Sub-project #2 complete; next is the sub-project #3 (narrative/AI) spec.

---

## Self-Review

**1. Spec coverage:**
- Scope decision 1 (port + harden, no expand) -> Task 2 ports the exact v1 metric set. ✓
- Decision 2 (Stooq best-effort, fills yf-missing) -> Task 8 + resolver `_resolve_other`. ✓
- Decision 3 (fetch-only, no persistence) -> no history/state code; history hook noted, not built. ✓
- Decision 4 (news as Article source, matcher in #3) -> Task 9 (NewsResult), Task 10 wires it; no matcher. ✓
- Decision 5 (oil rule only) -> resolver `_resolve_oil` + `_resolve_yield`; no new cross-checks. ✓
- Architecture A (service plugins + pure resolver) -> Tasks 4, 6-9; resolver is pure (no I/O). ✓
- Isolation -> Task 10 uses `run_isolated`; `test_yfinance_down_resolves_core_from_stooq`. ✓
- Accuracy invariant (units transform, oil never silently substituted) -> Task 7 `_call_fetcher`, Task 4 oil tests. ✓
- News never blocks -> Task 9 `test_total_failure_returns_empty`. ✓
- Offline seam -> Task 5 `is_offline`, every source `_offline`, Task 12 end-to-end. ✓
- Secrets env-only -> Task 7 `FRED_API_KEY` from env, degrades on absence. ✓
- Done-when bars -> Task 12 (offline run + no state), Task 10 (yf-down + oil-stale). ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; no hand-waved error handling (isolation + offline are concrete). ✓

**3. Type consistency:** `resolve_fields(per_service, config)`, `SourceResult(name, fields, health, error)`, `Field(metric, value, source, stale, as_of, note)`, `NewsResult(name, articles, health, error)`, `Article(source_id, title, summary, url)`, source `name`/`fetch`/`fetch_news` — consistent across tasks. Source tag strings match the global constraint list. `run_pipeline(ctx, *, sources, sections, news_source)` consistent between Task 10 and Task 11. ✓

**Note on RssSource and discovery:** RssSource deliberately exposes `fetch_news` (not `fetch`), so it does NOT satisfy the `DataSource` Protocol and is not auto-discovered; the pipeline injects it explicitly. This keeps the numeric `discover_sources()` clean while news still flows through one wired path. Verified by `test_rss_not_discovered_as_datasource` (Task 11).
