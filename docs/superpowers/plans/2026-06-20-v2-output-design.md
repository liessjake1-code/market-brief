# v2 Output / Design (Sub-project #4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn v2's frozen typed `BriefContext` into an email-ready HTML brief with inline CID charts, matching v1's shipped "The Tape" design in structure while refreshing its visuals within spec §6.5.

**Architecture:** Three testable layers between `BriefContext` and the email: enriched per-section builders (one file each, the existing `Section` protocol) → a pure `assemble/` layer that composes a `BriefView` (diff line, At-a-Glance, Top Story float, live fence, degrade banner) → a dumb render layer (ported+restyled matplotlib charts, a logic-free Jinja template, MIME assembly). Trust-critical rules (stale exclusion, settled/live fence, mechanical suppression, grounding) live in typed Python, never in the template.

**Tech Stack:** Python 3.12, Pydantic (frozen models), Jinja2, matplotlib (Agg). uv venv at `v2/.venv`. Tests with `cd v2 && ./.venv/bin/python -m pytest`.

## Global Constraints

- Branch `build/v2`; mirrors to origin at every commit/gate; never `main`; no auto-PR.
- Run tests: `cd v2 && ./.venv/bin/python -m pytest` (bash cwd does NOT persist; cd each call). Run git from repo root using `v2/` paths.
- uv-managed venv (NO pip). Add deps with `uv pip install --python .venv/bin/python <pkg>` AND to `v2/pyproject.toml`.
- All models frozen/immutable (`ConfigDict(frozen=True)`); never mutate, always `.model_copy(update=...)` / construct new.
- House style (spec §2): no em dashes, no emojis, plain declarative prose. Applies to all copy strings and quiet lines.
- Tests never hit the live API or network; reuse the offline seam (`MARKET_BRIEF_OFFLINE=1`) and fake clients.
- Files focused (<800 lines, target <150 per section builder). Many small files > few large.
- Coverage target ≥ 80%.
- Do NOT touch the v1 app (root `brief.py`, `engine/`, `render/`, `sources/`). v1 keeps sending daily.
- `--no-send` MUST imply no state write (never touch `last_run.json`).
- §6.5 palette (exact hex): ink navy `#13202E`, paper `#FBFAF7`, card white `#FFFFFF`, hairline `#E4E0D7`, gold rule `#B0892F`, green `#197A4B`, red `#BC3B2E`, grey `#6B7785`. Green/red carry direction ONLY.
- §6.5 fonts: Georgia (serif fallback) masthead; `Consolas, "SFMono-Regular", monospace` for every figure. Email-safe: single-column table layout, fully inline styles.

---

### Task 1: Enriched view-model types and enums

**Files:**
- Modify: `v2/marketbrief/core/enums.py` (add `Direction`, `ChartKind`)
- Modify: `v2/marketbrief/core/models.py` (add view-model models; enrich `SectionVM`)
- Test: `v2/tests/test_viewmodels.py`

**Interfaces:**
- Consumes: existing `BaseModel`, `ConfigDict` patterns in `core/models.py`.
- Produces: `Direction`, `ChartKind` enums; `FigureCell`, `StatRow`, `WhyLine`, `ChartRef`, `GlanceRow`, `MoverRow`, `SparkRef`, `LiveSnapshot`, `BriefView` models; enriched `SectionVM` with fields `id, title, order, quiet, lead: WhyLine, stat_rows: list[StatRow], why_lines: list[WhyLine], charts: list[ChartRef], movers: list[MoverRow], sparklines: list[SparkRef], is_promoted: bool`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_viewmodels.py
from marketbrief.core.enums import Direction, ChartKind
from marketbrief.core.models import (
    FigureCell, StatRow, WhyLine, ChartRef, GlanceRow, MoverRow, SparkRef,
    SectionVM, LiveSnapshot, BriefView,
)


def test_figurecell_defaults():
    c = FigureCell(metric_label="S&P", value_str="5,000", change_str="+0.4%",
                   direction=Direction.UP)
    assert c.stale is False and c.mechanical is False and c.source_url is None


def test_sectionvm_enriched_shape():
    lead = WhyLine(text="Indices little changed; no clear catalyst.", hedged=True)
    s = SectionVM(id="us_equities", title="US Equities", order=1, quiet=True, lead=lead)
    assert s.stat_rows == [] and s.why_lines == [] and s.is_promoted is False


def test_models_are_frozen():
    c = FigureCell(metric_label="x", value_str="1", change_str="0", direction=Direction.FLAT)
    import pytest
    with pytest.raises(Exception):
        c.stale = True


def test_briefview_compose():
    bv = BriefView(diff_line="Markets little changed overnight.", glance_rows=[],
                   sections=[], live=None, degraded=False, banner_text=None)
    assert bv.live is None and bv.degraded is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_viewmodels.py -v`
Expected: FAIL with ImportError (Direction / FigureCell not defined).

- [ ] **Step 3: Add enums**

```python
# append to v2/marketbrief/core/enums.py
class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class ChartKind(str, Enum):
    BAR = "bar"
    LINE = "line"
    CURVE = "curve"
    SPARK = "spark"
```

- [ ] **Step 4: Add view-model models and enrich SectionVM**

```python
# in v2/marketbrief/core/models.py — add import and models.
# update the import line to include the new enums:
from marketbrief.core.enums import SourceHealth, Verdict, Direction, ChartKind

class FigureCell(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_label: str
    value_str: str
    change_str: str
    direction: Direction
    source_url: str | None = None
    stale: bool = False
    mechanical: bool = False


class StatRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    label: str
    cells: list[FigureCell] = PField(default_factory=list)


class WhyLine(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    source_url: str | None = None
    source_label: str | None = None
    hedged: bool = False


class ChartRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    cid: str
    alt: str
    kind: ChartKind


class GlanceRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    category: str
    latest: str
    why_brief: str
    is_live: bool = False


class MoverRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    ticker: str
    favicon_url: str | None
    value_str: str
    direction: Direction
    why: str
    source_url: str | None = None


class SparkRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    ticker: str
    cid: str


class LiveSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    as_of_label: str
    rows: list[FigureCell] = PField(default_factory=list)
    is_premarket: bool = True


class BriefView(BaseModel):
    model_config = ConfigDict(frozen=True)
    diff_line: str
    glance_rows: list[GlanceRow] = PField(default_factory=list)
    sections: list["SectionVM"] = PField(default_factory=list)
    live: LiveSnapshot | None = None
    degraded: bool = False
    banner_text: str | None = None
```

Replace the existing stub `SectionVM` with:

```python
class SectionVM(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    order: int
    quiet: bool = False
    lead: WhyLine
    stat_rows: list[StatRow] = PField(default_factory=list)
    why_lines: list[WhyLine] = PField(default_factory=list)
    charts: list[ChartRef] = PField(default_factory=list)
    movers: list[MoverRow] = PField(default_factory=list)
    sparklines: list[SparkRef] = PField(default_factory=list)
    is_promoted: bool = False
```

Note: the old `SectionVM` had `body: str` and was not frozen. Removing `body` and making it frozen is intentional (the enriched model replaces it). Tasks 2+ and the renderer use the new shape; the old `render/html.py` and `sections/summary.py` are replaced in Tasks 12 and 3.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_viewmodels.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/core/enums.py v2/marketbrief/core/models.py v2/tests/test_viewmodels.py
git commit -m "feat(v2): enriched view-model types for output layer (gate 4)"
```

---

### Task 2: Section formatting helpers (figure_for, source_url, quiet lines)

**Files:**
- Create: `v2/marketbrief/render/source_links.py` (port from v1, retarget import)
- Create: `v2/marketbrief/sections/_format.py` (shared cell/why/quiet helpers)
- Test: `v2/tests/test_section_format.py`

**Interfaces:**
- Consumes: `Field` (from `core/models`), `SYMBOLS_BY_METRIC` (from `core/symbols`), `Direction`, `FigureCell`, `WhyLine`.
- Produces:
  - `source_links.source_url(metric: str) -> str | None`, `yahoo_ticker_url(ticker) -> str`, `favicon_url(domain: str | None) -> str | None`.
  - `_format.METRIC_LABELS: dict[str, str]`, `QUIET_LINES: dict[str, str]`, `SECTION_TITLES: dict[str, str]`.
  - `_format.figure_cell(metric: str, field: Field) -> FigureCell`.
  - `_format.direction_of(change: float | None) -> Direction`.
  - `_format.quiet_lead(section_id: str) -> WhyLine` (hedged=True, no source).

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_section_format.py
from marketbrief.core.enums import Direction
from marketbrief.core.models import Field
from marketbrief.render.source_links import source_url, favicon_url, yahoo_ticker_url
from marketbrief.sections._format import (
    figure_cell, direction_of, quiet_lead, METRIC_LABELS, QUIET_LINES,
)


def test_source_url_yield_is_fred():
    assert "fred.stlouisfed.org" in source_url("ust10y")


def test_source_url_index_is_yahoo():
    assert "finance.yahoo.com" in source_url("sp500")


def test_source_url_unknown_is_none():
    assert source_url("not_a_metric") is None


def test_favicon_none_domain():
    assert favicon_url(None) is None


def test_direction_of():
    assert direction_of(0.4) is Direction.UP
    assert direction_of(-0.4) is Direction.DOWN
    assert direction_of(0.0) is Direction.FLAT
    assert direction_of(None) is Direction.FLAT


def test_figure_cell_stale_flag_propagates():
    f = Field(metric="sp500", value=5000.0, source="yfinance", stale=True)
    cell = figure_cell("sp500", f)
    assert cell.stale is True
    assert cell.metric_label == "S&P"
    assert "finance.yahoo.com" in cell.source_url


def test_quiet_lead_is_hedged_and_sourceless():
    w = quiet_lead("us_equities")
    assert w.hedged is True and w.source_url is None
    assert "no clear catalyst" in w.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_section_format.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Port source_links.py**

Copy `render/source_links.py` from v1 verbatim into `v2/marketbrief/render/source_links.py`, changing only the import line `from sources.symbols import SYMBOLS_BY_METRIC` to `from marketbrief.core.symbols import SYMBOLS_BY_METRIC`. (Everything else — `source_url`, `yahoo_ticker_url`, `favicon_url`, `_is_yield_metric` — is unchanged.)

- [ ] **Step 4: Create _format.py**

```python
# v2/marketbrief/sections/_format.py
from __future__ import annotations
from marketbrief.core.enums import Direction
from marketbrief.core.models import Field, FigureCell, WhyLine
from marketbrief.render.source_links import source_url

METRIC_LABELS: dict[str, str] = {
    "sp500": "S&P", "nasdaq": "Nasdaq", "dow": "Dow", "russell": "Russell",
    "ust10y": "10Y", "ust2y": "2Y", "dxy": "DXY", "hy_spread": "HY spread",
    "wti": "WTI", "gold": "Gold", "copper": "Copper",
    "btc": "BTC", "eth": "ETH", "vix": "VIX",
    "cpi_yoy": "CPI YoY", "pce_yoy": "PCE YoY", "fed_funds": "Fed funds",
}

SECTION_TITLES: dict[str, str] = {
    "us_equities": "US Equities", "rates_and_dollar": "Rates and the Dollar",
    "commodities": "Commodities", "washington": "Washington and Policy",
    "movers": "Movers", "economic_data_scorecard": "Economic Data Scorecard",
    "earnings_on_deck": "Earnings on Deck", "watchlist": "Watchlist",
    "crypto": "Crypto", "volatility_breadth": "Volatility and Breadth",
    "what_to_watch_today": "What to Watch Today",
}

# Honest one-line fallbacks (spec §2, §5.6). No em dashes, no emojis.
QUIET_LINES: dict[str, str] = {
    "us_equities": "Indices little changed; no clear catalyst.",
    "rates_and_dollar": "Rates and the dollar steady; nothing to read into it.",
    "commodities": "Commodities quiet; no clear catalyst.",
    "washington": "No market-moving policy news flagged this morning.",
    "movers": "No single-stock movers flagged from the curated universe.",
    "economic_data_scorecard": "No major economic releases on the board.",
    "earnings_on_deck": "No notable earnings flagged before the open.",
    "watchlist": "Watchlist is empty. Add tickers in config.yaml before first send.",
    "crypto": "Crypto little changed; risk appetite neutral.",
    "volatility_breadth": "VIX flat, no hedging demand, nothing to read into it.",
    "what_to_watch_today": "No scheduled events flagged for today.",
}


def direction_of(change: float | None) -> Direction:
    if change is None or change == 0.0:
        return Direction.FLAT
    return Direction.UP if change > 0 else Direction.DOWN


def _fmt_value(field: Field) -> str:
    if field.value is None:
        return "n/a"
    return f"{field.value:,.2f}"


def figure_cell(metric: str, field: Field, *, change: float | None = None) -> FigureCell:
    return FigureCell(
        metric_label=METRIC_LABELS.get(metric, metric),
        value_str=_fmt_value(field),
        change_str="" if change is None else f"{change:+.2f}",
        direction=direction_of(change),
        source_url=source_url(metric),
        stale=field.stale,
    )


def quiet_lead(section_id: str) -> WhyLine:
    return WhyLine(text=QUIET_LINES[section_id], source_url=None, hedged=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_section_format.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/render/source_links.py v2/marketbrief/sections/_format.py v2/tests/test_section_format.py
git commit -m "feat(v2): section formatting helpers + ported source links"
```

---

### Task 3: First section builder (US Equities) + narration-to-whyline bridge

This task establishes the section-builder pattern every later section follows. It also replaces the stub `sections/summary.py`.

**Files:**
- Delete: `v2/marketbrief/sections/summary.py` (stub, replaced)
- Create: `v2/marketbrief/sections/_base.py` (shared narration→WhyLine bridge)
- Create: `v2/marketbrief/sections/equities.py`
- Test: `v2/tests/test_section_equities.py`

**Interfaces:**
- Consumes: `BriefContext`, `ctx.resolved_fields: dict[str, Field]`, `ctx.narration: dict[str, NarratedWhy]`, `_format` helpers, `figure_cell`, `quiet_lead`.
- Produces:
  - `_base.why_lines_from_narration(section_id, ctx) -> tuple[WhyLine, list[WhyLine]]` returning `(lead, deep_lines)`. When narration is missing/degraded/quiet, `lead = quiet_lead(section_id)` and `deep_lines = []`. A narrated `Cause` with no `cause_source_id` yields `hedged=True`.
  - `equities.EquitiesSection` with `id="us_equities"`, `order=1`, `build(ctx) -> SectionVM | None`, `is_quiet(ctx) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_section_equities.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Field, NarratedWhy, Cause
from marketbrief.sections.equities import EquitiesSection


def _ctx(fields, narration=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), resolved_fields=fields,
                        narration=narration or {})


def test_quiet_when_no_fields():
    vm = EquitiesSection().build(_ctx({}))
    assert vm.id == "us_equities" and vm.quiet is True
    assert "no clear catalyst" in vm.lead.text.lower()
    assert vm.stat_rows == []


def test_full_read_with_fields_and_narration():
    fields = {"sp500": Field(metric="sp500", value=5000.0, source="yfinance"),
              "nasdaq": Field(metric="nasdaq", value=16000.0, source="yfinance")}
    nar = {"us_equities": NarratedWhy(
        section_id="us_equities", text="Stocks rose on soft inflation.",
        causes=[Cause(claim="Stocks rose on soft inflation.",
                      cause_source_id="art1", verdict=Verdict.PASS)])}
    vm = EquitiesSection().build(_ctx(fields, nar))
    assert vm.quiet is False
    assert len(vm.stat_rows[0].cells) == 2
    assert vm.lead.text == "Stocks rose on soft inflation."
    assert vm.lead.hedged is False


def test_stale_field_marked_in_cell():
    fields = {"sp500": Field(metric="sp500", value=5000.0, source="yfinance", stale=True)}
    vm = EquitiesSection().build(_ctx(fields))
    assert vm.stat_rows[0].cells[0].stale is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_section_equities.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Delete the stub and create the base bridge**

```bash
git rm v2/marketbrief/sections/summary.py
```

```python
# v2/marketbrief/sections/_base.py
from __future__ import annotations
from marketbrief.core.models import WhyLine
from marketbrief.sections._format import quiet_lead
from marketbrief.render.source_links import source_url  # noqa: F401  (kept for parity)


def why_lines_from_narration(section_id: str, ctx) -> tuple[WhyLine, list[WhyLine]]:
    """Bridge NarratedWhy -> (lead WhyLine, deep WhyLines).

    Falls back to the honest quiet line when narration is absent, degraded, or
    has no usable causes. An unsourced cause is always hedged (spec §2 grounding).
    """
    why = ctx.narration.get(section_id)
    if why is None or why.degraded or not why.text:
        return quiet_lead(section_id), []
    has_source = any(c.cause_source_id for c in why.causes)
    lead = WhyLine(text=why.text, source_url=None, hedged=not has_source)
    deep: list[WhyLine] = []
    for c in why.causes:
        deep.append(WhyLine(text=c.claim, source_url=None,
                            hedged=c.cause_source_id is None))
    return lead, deep
```

- [ ] **Step 4: Create equities.py**

```python
# v2/marketbrief/sections/equities.py
from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("sp500", "nasdaq", "dow", "russell")


class EquitiesSection:
    id = "us_equities"
    order = 1

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        stat_rows = [StatRow(label="Indices", cells=cells)] if cells else []
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order,
            quiet=quiet, lead=lead, stat_rows=stat_rows,
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_section_equities.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run full suite to confirm summary-stub removal broke nothing unexpected**

Run: `cd v2 && ./.venv/bin/python -m pytest -q`
Expected: any failures are ONLY in tests that referenced the old `SectionVM.body` or `summary` stub. Note them; they are fixed in Task 12 (renderer) and Task 13 (pipeline/e2e). If a pre-existing test asserts the old shape, update it to the new shape in this commit.

- [ ] **Step 7: Commit**

```bash
git add v2/marketbrief/sections/_base.py v2/marketbrief/sections/equities.py v2/tests/test_section_equities.py
git commit -m "feat(v2): US Equities section builder + narration bridge (section pattern)"
```

---

### Task 4: Rates, Commodities, Crypto, Volatility sections (number-driven)

These four follow the Task 3 pattern exactly; they differ only in `id`, `order`, `title`, and their metric tuple. Each is its own file.

**Files:**
- Create: `v2/marketbrief/sections/rates.py`, `commodities.py`, `crypto.py`, `volatility.py`
- Test: `v2/tests/test_sections_numeric.py`

**Interfaces:**
- Produces: `RatesSection(id="rates_and_dollar", order=2)`, `CommoditiesSection(id="commodities", order=3)`, `CryptoSection(id="crypto", order=9)`, `VolatilitySection(id="volatility_breadth", order=10)` — each with `build`/`is_quiet` like Task 3.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_sections_numeric.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.core.models import Field
from marketbrief.sections.rates import RatesSection
from marketbrief.sections.commodities import CommoditiesSection
from marketbrief.sections.crypto import CryptoSection
from marketbrief.sections.volatility import VolatilitySection


def _ctx(fields):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), resolved_fields=fields)


def _f(m, v):
    return {m: Field(metric=m, value=v, source="yfinance")}


def test_rates_full_and_quiet():
    vm = RatesSection().build(_ctx({**_f("ust10y", 4.3), **_f("ust2y", 4.0),
                                    **_f("dxy", 104.0)}))
    assert vm.id == "rates_and_dollar" and vm.quiet is False
    assert len(vm.stat_rows[0].cells) == 3
    assert RatesSection().build(_ctx({})).quiet is True


def test_commodities():
    vm = CommoditiesSection().build(_ctx({**_f("wti", 78.0), **_f("gold", 2300.0)}))
    assert vm.id == "commodities" and len(vm.stat_rows[0].cells) == 2


def test_crypto():
    vm = CryptoSection().build(_ctx({**_f("btc", 65000.0), **_f("eth", 3500.0)}))
    assert vm.id == "crypto" and len(vm.stat_rows[0].cells) == 2


def test_volatility():
    vm = VolatilitySection().build(_ctx(_f("vix", 14.0)))
    assert vm.id == "volatility_breadth" and len(vm.stat_rows[0].cells) == 1
    assert VolatilitySection().build(_ctx({})).quiet is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_sections_numeric.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create the four files**

```python
# v2/marketbrief/sections/rates.py
from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("ust10y", "ust2y", "dxy")


class RatesSection:
    id = "rates_and_dollar"
    order = 2

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order, quiet=quiet,
            lead=lead, stat_rows=[StatRow(label="Rates and dollar", cells=cells)] if cells else [],
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
```

```python
# v2/marketbrief/sections/commodities.py
from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("wti", "gold")


class CommoditiesSection:
    id = "commodities"
    order = 3

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order, quiet=quiet,
            lead=lead, stat_rows=[StatRow(label="Commodities", cells=cells)] if cells else [],
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
```

```python
# v2/marketbrief/sections/crypto.py
from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("btc", "eth")


class CryptoSection:
    id = "crypto"
    order = 9

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order, quiet=quiet,
            lead=lead, stat_rows=[StatRow(label="Crypto", cells=cells)] if cells else [],
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
```

```python
# v2/marketbrief/sections/volatility.py
from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("vix",)


class VolatilitySection:
    id = "volatility_breadth"
    order = 10

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order, quiet=quiet,
            lead=lead, stat_rows=[StatRow(label="Volatility", cells=cells)] if cells else [],
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_sections_numeric.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/sections/rates.py v2/marketbrief/sections/commodities.py v2/marketbrief/sections/crypto.py v2/marketbrief/sections/volatility.py v2/tests/test_sections_numeric.py
git commit -m "feat(v2): rates, commodities, crypto, volatility section builders"
```

---

### Task 5: Narrative-only sections (Washington, Economic Data, Earnings, What to Watch)

These four carry no settled price table; they are narration/quiet-line driven (Washington, Earnings, What-to-Watch) plus an econ-data scorecard placeholder that shows its FRED-derived rows when present. Each is its own file.

**Files:**
- Create: `v2/marketbrief/sections/washington.py`, `economic_data.py`, `earnings.py`, `what_to_watch.py`
- Test: `v2/tests/test_sections_narrative.py`

**Interfaces:**
- Produces: `WashingtonSection(id="washington", order=4)`, `EconomicDataSection(id="economic_data_scorecard", order=6)`, `EarningsSection(id="earnings_on_deck", order=7)`, `WhatToWatchSection(id="what_to_watch_today", order=11)`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_sections_narrative.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Verdict
from marketbrief.core.models import Field, NarratedWhy, Cause
from marketbrief.sections.washington import WashingtonSection
from marketbrief.sections.economic_data import EconomicDataSection
from marketbrief.sections.earnings import EarningsSection
from marketbrief.sections.what_to_watch import WhatToWatchSection


def _ctx(narration=None, fields=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), narration=narration or {},
                        resolved_fields=fields or {})


def test_washington_quiet():
    vm = WashingtonSection().build(_ctx())
    assert vm.id == "washington" and vm.quiet is True
    assert "no market-moving policy" in vm.lead.text.lower()


def test_washington_with_narration():
    nar = {"washington": NarratedWhy(section_id="washington", text="Fed held rates.",
            causes=[Cause(claim="Fed held rates.", cause_source_id="art2", verdict=Verdict.PASS)])}
    vm = WashingtonSection().build(_ctx(nar))
    assert vm.quiet is False and vm.lead.text == "Fed held rates."


def test_econ_data_rows_when_fields_present():
    fields = {"cpi_yoy": Field(metric="cpi_yoy", value=3.1, source="fred")}
    vm = EconomicDataSection().build(_ctx(fields=fields))
    assert vm.id == "economic_data_scorecard"
    assert len(vm.stat_rows[0].cells) == 1


def test_earnings_quiet():
    assert EarningsSection().build(_ctx()).quiet is True


def test_what_to_watch_quiet():
    assert WhatToWatchSection().build(_ctx()).quiet is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_sections_narrative.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create the four files**

```python
# v2/marketbrief/sections/washington.py
from __future__ import annotations
from marketbrief.core.models import SectionVM
from marketbrief.sections._format import SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration


class WashingtonSection:
    id = "washington"
    order = 4

    def build(self, ctx) -> SectionVM | None:
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=quiet, lead=lead, why_lines=[] if quiet else deep)

    def is_quiet(self, ctx) -> bool:
        why = ctx.narration.get(self.id)
        return why is None or why.degraded or not why.text
```

```python
# v2/marketbrief/sections/economic_data.py
from __future__ import annotations
from marketbrief.core.models import SectionVM, StatRow
from marketbrief.sections._format import figure_cell, SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration

_METRICS = ("cpi_yoy", "pce_yoy", "fed_funds")


class EconomicDataSection:
    id = "economic_data_scorecard"
    order = 6

    def build(self, ctx) -> SectionVM | None:
        cells = [figure_cell(m, ctx.resolved_fields[m])
                 for m in _METRICS if m in ctx.resolved_fields]
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(
            id=self.id, title=SECTION_TITLES[self.id], order=self.order, quiet=quiet,
            lead=lead, stat_rows=[StatRow(label="Scorecard", cells=cells)] if cells else [],
            why_lines=[] if quiet else deep,
        )

    def is_quiet(self, ctx) -> bool:
        return not any(m in ctx.resolved_fields for m in _METRICS)
```

```python
# v2/marketbrief/sections/earnings.py
from __future__ import annotations
from marketbrief.core.models import SectionVM
from marketbrief.sections._format import SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration


class EarningsSection:
    id = "earnings_on_deck"
    order = 7

    def build(self, ctx) -> SectionVM | None:
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=quiet, lead=lead, why_lines=[] if quiet else deep)

    def is_quiet(self, ctx) -> bool:
        why = ctx.narration.get(self.id)
        return why is None or why.degraded or not why.text
```

```python
# v2/marketbrief/sections/what_to_watch.py
from __future__ import annotations
from marketbrief.core.models import SectionVM
from marketbrief.sections._format import SECTION_TITLES
from marketbrief.sections._base import why_lines_from_narration


class WhatToWatchSection:
    id = "what_to_watch_today"
    order = 11

    def build(self, ctx) -> SectionVM | None:
        quiet = self.is_quiet(ctx)
        lead, deep = why_lines_from_narration(self.id, ctx)
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=quiet, lead=lead, why_lines=[] if quiet else deep)

    def is_quiet(self, ctx) -> bool:
        why = ctx.narration.get(self.id)
        return why is None or why.degraded or not why.text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_sections_narrative.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/sections/washington.py v2/marketbrief/sections/economic_data.py v2/marketbrief/sections/earnings.py v2/marketbrief/sections/what_to_watch.py v2/tests/test_sections_narrative.py
git commit -m "feat(v2): washington, econ-data, earnings, what-to-watch section builders"
```

---

### Task 6: Movers and Watchlist sections (favicon rows)

Movers and Watchlist build `MoverRow`s with favicons (spec §6.5 favicons in these two sections only). Movers defaults to watchlist-movers-only (spec §7 best-effort rule); with no per-stock data both are quiet. Watchlist reads `config.watchlist` tickers.

**Files:**
- Create: `v2/marketbrief/sections/movers.py`, `watchlist.py`
- Create: `v2/marketbrief/sections/_tickers.py` (ticker→domain map, ported subset from v1)
- Test: `v2/tests/test_sections_stocks.py`

**Interfaces:**
- Consumes: `config.watchlist: list[str]`, `yahoo_ticker_url`, `favicon_url`, `_tickers.DOMAIN_BY_TICKER`.
- Produces: `MoversSection(id="movers", order=5)`, `WatchlistSection(id="watchlist", order=8)`. `_tickers.domain_for(ticker) -> str | None`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_sections_stocks.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.sections.movers import MoversSection
from marketbrief.sections.watchlist import WatchlistSection


def _ctx(watchlist=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(watchlist=watchlist or []))


def test_movers_quiet_with_no_data():
    vm = MoversSection().build(_ctx())
    assert vm.id == "movers" and vm.quiet is True
    assert vm.movers == []


def test_watchlist_quiet_when_empty():
    vm = WatchlistSection().build(_ctx([]))
    assert vm.id == "watchlist" and vm.quiet is True
    assert "watchlist is empty" in vm.lead.text.lower()


def test_watchlist_rows_when_populated():
    vm = WatchlistSection().build(_ctx(["AAPL", "MSFT"]))
    assert vm.quiet is False
    assert [r.ticker for r in vm.movers] == ["AAPL", "MSFT"]
    assert vm.movers[0].source_url.endswith("AAPL")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_sections_stocks.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create _tickers.py**

```python
# v2/marketbrief/sections/_tickers.py
from __future__ import annotations

# Minimal ticker->domain map for favicons (spec §6.5). Extend as the watchlist grows.
DOMAIN_BY_TICKER: dict[str, str] = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "NVDA": "nvidia.com",
    "AMZN": "amazon.com", "GOOGL": "abc.xyz", "META": "meta.com",
    "TSLA": "tesla.com", "JPM": "jpmorganchase.com", "XOM": "exxonmobil.com",
}


def domain_for(ticker: str) -> str | None:
    return DOMAIN_BY_TICKER.get(ticker.upper())
```

- [ ] **Step 4: Create movers.py and watchlist.py**

```python
# v2/marketbrief/sections/movers.py
from __future__ import annotations
from marketbrief.core.models import SectionVM
from marketbrief.sections._format import SECTION_TITLES, quiet_lead


class MoversSection:
    id = "movers"
    order = 5

    def build(self, ctx) -> SectionVM | None:
        # Best-effort: per-stock universe data is deferred; default to quiet
        # (spec §7 movers best-effort rule). Real rows arrive with the universe screen.
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=True, lead=quiet_lead(self.id), movers=[])

    def is_quiet(self, ctx) -> bool:
        return True
```

```python
# v2/marketbrief/sections/watchlist.py
from __future__ import annotations
from marketbrief.core.enums import Direction
from marketbrief.core.models import SectionVM, MoverRow, WhyLine
from marketbrief.sections._format import SECTION_TITLES, quiet_lead
from marketbrief.sections._tickers import domain_for
from marketbrief.render.source_links import yahoo_ticker_url, favicon_url


class WatchlistSection:
    id = "watchlist"
    order = 8

    def build(self, ctx) -> SectionVM | None:
        tickers = list(ctx.config.watchlist)
        if not tickers:
            return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                             quiet=True, lead=quiet_lead(self.id), movers=[])
        rows = [MoverRow(ticker=t, favicon_url=favicon_url(domain_for(t)),
                         value_str="n/a", direction=Direction.FLAT, why="",
                         source_url=yahoo_ticker_url(t)) for t in tickers]
        lead = WhyLine(text="Your tracked names.", source_url=None, hedged=True)
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=False, lead=lead, movers=rows)

    def is_quiet(self, ctx) -> bool:
        return not ctx.config.watchlist
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_sections_stocks.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/sections/_tickers.py v2/marketbrief/sections/movers.py v2/marketbrief/sections/watchlist.py v2/tests/test_sections_stocks.py
git commit -m "feat(v2): movers + watchlist section builders (favicon rows)"
```

---

### Task 7: Config extension (chart toggles)

**Files:**
- Modify: `v2/marketbrief/core/config.py` (add `ChartsConfig`, add `charts` to `Config`)
- Test: `v2/tests/test_config_charts.py`

**Interfaces:**
- Produces: `ChartsConfig` with bool fields `equities=True, rates=True, commodities=True, vix=False, movers=False, crypto=False, scorecard=False, sparklines=False`; `Config.charts: ChartsConfig`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_config_charts.py
from marketbrief.core.config import Config, ChartsConfig


def test_default_on_charts():
    c = Config()
    assert c.charts.equities is True and c.charts.rates is True and c.charts.commodities is True


def test_default_off_charts():
    c = Config()
    assert c.charts.vix is False and c.charts.movers is False and c.charts.crypto is False
    assert c.charts.scorecard is False and c.charts.sparklines is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_config_charts.py -v`
Expected: FAIL (ImportError: ChartsConfig).

- [ ] **Step 3: Extend config.py**

```python
# in v2/marketbrief/core/config.py — add before class Config, then add field.
class ChartsConfig(BaseModel):
    equities: bool = True       # default on (spec §6)
    rates: bool = True          # default on
    commodities: bool = True    # default on
    vix: bool = False
    movers: bool = False
    crypto: bool = False
    scorecard: bool = False
    sparklines: bool = False    # auto-on once watchlist populated (handled in render)
```

Add to `Config`:

```python
    charts: ChartsConfig = Field(default_factory=ChartsConfig)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_config_charts.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/config.py v2/tests/test_config_charts.py
git commit -m "feat(v2): ChartsConfig toggles (3 default-on per spec §6)"
```

---

### Task 8: assemble/diff_line + assemble/glance

**Files:**
- Create: `v2/marketbrief/assemble/__init__.py`, `diff_line.py`, `glance.py`
- Test: `v2/tests/test_assemble_top.py`

**Interfaces:**
- Consumes: `ctx.resolved_fields`, `ctx.prev_state: dict`, built `list[SectionVM]`, `_format` helpers.
- Produces:
  - `diff_line.build_diff_line(ctx) -> str`. Excludes stale fields. Returns "Markets little changed overnight." when nothing crosses a threshold or no prior state.
  - `glance.build_glance_rows(ctx, sections) -> list[GlanceRow]`. One row per glance category; the "This morning" row has `is_live=True`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_assemble_top.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.core.models import Field
from marketbrief.assemble.diff_line import build_diff_line
from marketbrief.assemble.glance import build_glance_rows


def _ctx(fields=None, prev=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), resolved_fields=fields or {}, prev_state=prev or {})


def test_diff_line_no_prior_state():
    assert build_diff_line(_ctx()) == "Markets little changed overnight."


def test_diff_line_excludes_stale():
    fields = {"sp500": Field(metric="sp500", value=5100.0, source="yfinance", stale=True)}
    prev = {"fields": {"sp500": 5000.0}}
    # stale field cannot drive the diff line
    assert build_diff_line(_ctx(fields, prev)) == "Markets little changed overnight."


def test_diff_line_reports_move():
    fields = {"sp500": Field(metric="sp500", value=5100.0, source="yfinance")}
    prev = {"fields": {"sp500": 5000.0}}
    line = build_diff_line(_ctx(fields, prev))
    assert "S&P" in line and "%" in line


def test_glance_has_live_row():
    rows = build_glance_rows(_ctx(), sections=[])
    live = [r for r in rows if r.is_live]
    assert len(live) == 1 and "morning" in live[0].category.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_assemble_top.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create the assemble package and diff_line.py**

```python
# v2/marketbrief/assemble/__init__.py
```

```python
# v2/marketbrief/assemble/diff_line.py
from __future__ import annotations
from marketbrief.sections._format import METRIC_LABELS

NO_CHANGE = "Markets little changed overnight."
_PCT_THRESHOLD = 0.5  # report a settled index move in the diff line at >= 0.5%
_DIFF_METRICS = ("sp500", "nasdaq", "dow", "russell")


def build_diff_line(ctx) -> str:
    prev_fields = (ctx.prev_state or {}).get("fields", {})
    best_label, best_pct = None, 0.0
    for metric in _DIFF_METRICS:
        field = ctx.resolved_fields.get(metric)
        if field is None or field.stale or field.value is None:
            continue  # stale fields are excluded from the diff line (spec §7.5)
        prev = prev_fields.get(metric)
        if not prev:
            continue
        pct = (field.value - prev) / prev * 100.0
        if abs(pct) >= _PCT_THRESHOLD and abs(pct) > abs(best_pct):
            best_label, best_pct = METRIC_LABELS.get(metric, metric), pct
    if best_label is None:
        return NO_CHANGE
    return f"{best_label} {best_pct:+.1f}% since yesterday's close."
```

- [ ] **Step 4: Create glance.py**

```python
# v2/marketbrief/assemble/glance.py
from __future__ import annotations
from marketbrief.core.models import GlanceRow

# At-a-Glance categories in spec §4.1 order. "This morning" is the one live row.
_CATEGORIES = (
    ("Markets", False), ("Rates and dollar", False), ("Commodities", False),
    ("Crypto", False), ("Volatility", False), ("This morning", True),
    ("Today's events", False), ("Earnings", False), ("Washington", False),
    ("Bottom line", False),
)


def build_glance_rows(ctx, sections) -> list[GlanceRow]:
    by_id = {s.id: s for s in sections}

    def latest_for(*ids: str) -> str:
        for sid in ids:
            s = by_id.get(sid)
            if s and s.stat_rows and s.stat_rows[0].cells:
                return ", ".join(c.value_str for c in s.stat_rows[0].cells)
        return "n/a"

    def why_for(*ids: str) -> str:
        for sid in ids:
            s = by_id.get(sid)
            if s:
                return s.lead.text
        return ""

    mapping = {
        "Markets": ("us_equities",),
        "Rates and dollar": ("rates_and_dollar",),
        "Commodities": ("commodities",),
        "Crypto": ("crypto",),
        "Volatility": ("volatility_breadth",),
        "Today's events": ("what_to_watch_today",),
        "Earnings": ("earnings_on_deck",),
        "Washington": ("washington",),
    }
    rows: list[GlanceRow] = []
    for category, is_live in _CATEGORIES:
        ids = mapping.get(category, ())
        rows.append(GlanceRow(
            category=category,
            latest="" if is_live or category == "Bottom line" else latest_for(*ids),
            why_brief=why_for(*ids) if ids else "",
            is_live=is_live,
        ))
    return rows
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_assemble_top.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/assemble/__init__.py v2/marketbrief/assemble/diff_line.py v2/marketbrief/assemble/glance.py v2/tests/test_assemble_top.py
git commit -m "feat(v2): assemble diff line + At-a-Glance rows (stale-excluded)"
```

---

### Task 9: assemble/topstory (Top Story float + mechanical suppression)

**Files:**
- Create: `v2/marketbrief/assemble/topstory.py`
- Test: `v2/tests/test_assemble_topstory.py`

**Interfaces:**
- Consumes: built `list[SectionVM]`, `ctx.run_date`, `ctx.numbers.values`, `data/mechanical_moves.yaml` (read via a small loader). For #4, the tier-one calendar trigger is read from `ctx.numbers`/config-less defaults; calendar wiring is deferred but the standardized-move path and mechanical suppression are implemented and tested.
- Produces: `topstory.order_sections(ctx, sections) -> list[SectionVM]`. Returns sections in spec §4.2 fallback order, with the promoted section pulled to the front and `is_promoted=True`. On a mechanical-move date, promotion is suppressed (sections stay in fallback order).
- Produces: `topstory.is_mechanical_date(run_date, path="data/mechanical_moves.yaml") -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_assemble_topstory.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode, Direction
from marketbrief.core.models import ComputedNumbers, SectionVM, WhyLine
from marketbrief.assemble.topstory import order_sections


def _sec(sid, order):
    return SectionVM(id=sid, title=sid, order=order, lead=WhyLine(text="x", hedged=True))


def _ctx(values=None):
    return BriefContext(run_date=date(2026, 6, 23), mode=RunMode.NO_SEND, config=Config(),
                        numbers=ComputedNumbers(values=values or {}))


_FALLBACK = ["us_equities", "rates_and_dollar", "commodities", "washington", "movers",
             "economic_data_scorecard", "earnings_on_deck", "watchlist", "crypto",
             "volatility_breadth", "what_to_watch_today"]


def test_fallback_order_when_no_trigger():
    secs = [_sec(s, i + 1) for i, s in enumerate(_FALLBACK)]
    out = order_sections(_ctx(), secs)
    assert [s.id for s in out] == _FALLBACK
    assert all(not s.is_promoted for s in out)


def test_large_rate_move_promotes_rates():
    secs = [_sec(s, i + 1) for i, s in enumerate(_FALLBACK)]
    # 10-year up >8bps drives promotion of rates_and_dollar (spec §5.2)
    out = order_sections(_ctx({"ust10y_change_bps": 12.0}), secs)
    assert out[0].id == "rates_and_dollar" and out[0].is_promoted is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_assemble_topstory.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create topstory.py**

```python
# v2/marketbrief/assemble/topstory.py
from __future__ import annotations
from datetime import date
from pathlib import Path
import yaml

# Fixed fallback order (spec §4.2).
FALLBACK_ORDER = (
    "us_equities", "rates_and_dollar", "commodities", "washington", "movers",
    "economic_data_scorecard", "earnings_on_deck", "watchlist", "crypto",
    "volatility_breadth", "what_to_watch_today",
)

# Standardized-move triggers (spec §5.2). Keyed by the ComputedNumbers value name.
_MOVE_TRIGGERS = (
    ("ust10y_change_bps", 8.0, "rates_and_dollar"),
    ("wti_change_pct", 3.0, "commodities"),
    ("sp500_change_pct", 1.0, "us_equities"),
)


def is_mechanical_date(run_date: date, path: str = "data/mechanical_moves.yaml") -> bool:
    p = Path(path)
    if not p.exists():
        return False
    data = yaml.safe_load(p.read_text()) or {}
    dates = data.get("dates", []) if isinstance(data, dict) else data
    return run_date.isoformat() in {str(d) for d in dates}


def _promoted_id(ctx) -> str | None:
    if is_mechanical_date(ctx.run_date):
        return None  # mechanical move: report but do not promote (spec §7.7)
    values = ctx.numbers.values
    best_id, best_excess = None, 0.0
    for name, trigger, section_id in _MOVE_TRIGGERS:
        v = values.get(name)
        if v is None:
            continue
        excess = abs(v) - trigger
        if excess > 0 and excess > best_excess:
            best_id, best_excess = section_id, excess
    return best_id


def order_sections(ctx, sections) -> list[SectionVM]:  # noqa: F821 (SectionVM via runtime)
    rank = {sid: i for i, sid in enumerate(FALLBACK_ORDER)}
    ordered = sorted(sections, key=lambda s: rank.get(s.id, 99))
    promoted = _promoted_id(ctx)
    if promoted is None:
        return ordered
    lead = [s for s in ordered if s.id == promoted]
    rest = [s for s in ordered if s.id != promoted]
    if not lead:
        return ordered
    promoted_vm = lead[0].model_copy(update={"is_promoted": True})
    return [promoted_vm, *rest]
```

Add `from marketbrief.core.models import SectionVM` at the top so the annotation resolves; remove the `# noqa` once added.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_assemble_topstory.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/assemble/topstory.py v2/tests/test_assemble_topstory.py
git commit -m "feat(v2): Top Story float ordering + mechanical-move suppression (§5, §7.7)"
```

---

### Task 10: assemble/fence + assemble/banner + assemble/brief_view

**Files:**
- Create: `v2/marketbrief/assemble/fence.py`, `banner.py`, `brief_view.py`
- Test: `v2/tests/test_assemble_fence_banner.py`

**Interfaces:**
- Consumes: `ctx.health: HealthReport`, `ctx.run_date`, a pull-time `datetime`, built+ordered sections, glance rows, diff line.
- Produces:
  - `fence.build_live_snapshot(pull_time_ct, rows) -> LiveSnapshot`. Label "Pre-market as of HH:MM CT" when `pull_time_ct.hour*60+minute < 8*60+30`, else "Early session as of HH:MM CT"; `is_premarket` set accordingly.
  - `banner.banner_text(health) -> str | None`. Returns a one-line banner when `health.degraded`, else None.
  - `brief_view.build_brief_view(ctx, ordered_sections, glance_rows, diff_line, live) -> BriefView`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_assemble_fence_banner.py
from datetime import datetime
from marketbrief.core.models import HealthReport
from marketbrief.assemble.fence import build_live_snapshot
from marketbrief.assemble.banner import banner_text


def test_premarket_label_before_open():
    snap = build_live_snapshot(datetime(2026, 6, 20, 8, 25), rows=[])
    assert snap.is_premarket is True and snap.as_of_label.startswith("Pre-market as of")
    assert "08:25 CT" in snap.as_of_label


def test_early_session_label_after_open():
    snap = build_live_snapshot(datetime(2026, 6, 20, 9, 5), rows=[])
    assert snap.is_premarket is False
    assert snap.as_of_label.startswith("Early session as of")


def test_banner_none_when_clean():
    assert banner_text(HealthReport(degraded=False)) is None


def test_banner_text_when_degraded():
    txt = banner_text(HealthReport(degraded=True))
    assert txt and "limited" in txt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_assemble_fence_banner.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create the three files**

```python
# v2/marketbrief/assemble/fence.py
from __future__ import annotations
from datetime import datetime
from marketbrief.core.models import LiveSnapshot, FigureCell

_OPEN_MINUTES = 8 * 60 + 30  # 8:30 AM CT cash open (spec §3.1)


def build_live_snapshot(pull_time_ct: datetime, rows: list[FigureCell]) -> LiveSnapshot:
    minutes = pull_time_ct.hour * 60 + pull_time_ct.minute
    is_pre = minutes < _OPEN_MINUTES
    word = "Pre-market" if is_pre else "Early session"
    label = f"{word} as of {pull_time_ct:%H:%M} CT"
    return LiveSnapshot(as_of_label=label, rows=rows, is_premarket=is_pre)
```

```python
# v2/marketbrief/assemble/banner.py
from __future__ import annotations
from marketbrief.core.models import HealthReport

_BANNER = ("Some sources returned limited data or could not be refreshed this morning. "
           "Read the figures with that in mind.")


def banner_text(health: HealthReport) -> str | None:
    return _BANNER if health.degraded else None
```

```python
# v2/marketbrief/assemble/brief_view.py
from __future__ import annotations
from marketbrief.core.models import BriefView, LiveSnapshot
from marketbrief.assemble.banner import banner_text


def build_brief_view(ctx, ordered_sections, glance_rows, diff_line,
                     live: LiveSnapshot | None) -> BriefView:
    text = banner_text(ctx.health)
    return BriefView(
        diff_line=diff_line, glance_rows=glance_rows, sections=ordered_sections,
        live=live, degraded=ctx.health.degraded, banner_text=text,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_assemble_fence_banner.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/assemble/fence.py v2/marketbrief/assemble/banner.py v2/marketbrief/assemble/brief_view.py v2/tests/test_assemble_fence_banner.py
git commit -m "feat(v2): live fence (time-aware label) + degrade banner + BriefView compose"
```

---

### Task 11: Charts (port + restyle to §6.5 palette)

**Files:**
- Create: `v2/marketbrief/render/charts.py` (port v1's `Chart` + builders, restyle)
- Create: `v2/marketbrief/render/chart_set.py` (build the default-on `ChartRef`s + CID→png map)
- Test: `v2/tests/test_charts.py`

**Interfaces:**
- Consumes: matplotlib (already a v1 dep; ensure installed in v2 venv), `ChartsConfig`, `ChartRef`, `ChartKind`.
- Produces:
  - `charts.Chart` dataclass (`cid: str`, `png: bytes`, `title: str`, `summary: str`).
  - `charts.index_change_bar(changes: dict[str, float], *, cid="chart_index") -> Chart | None` (ported).
  - `chart_set.build_charts(ctx) -> tuple[dict[str, bytes], dict[str, list[ChartRef]]]` returning `(png_by_cid, chartrefs_by_section_id)`. Honors `config.charts` toggles; sparklines auto-on when `config.watchlist` non-empty. On any chart build failure the chart is skipped (section renders without it).

- [ ] **Step 1: Ensure matplotlib + pyyaml are installed in the v2 venv**

Run:
```bash
cd v2 && ./.venv/bin/python -c "import matplotlib, yaml; print('ok')" || \
  uv pip install --python .venv/bin/python matplotlib pyyaml
```
If it installs, add `matplotlib` and `pyyaml` to `v2/pyproject.toml` dependencies.

- [ ] **Step 2: Write the failing test**

```python
# v2/tests/test_charts.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.render.charts import index_change_bar, Chart
from marketbrief.render.chart_set import build_charts


def _ctx(watchlist=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(watchlist=watchlist or []))


def test_index_change_bar_returns_png():
    chart = index_change_bar({"S&P": 0.4, "Nasdaq": 0.8, "Dow": 0.1, "Russell": -0.2})
    assert isinstance(chart, Chart)
    assert chart.png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_build_charts_default_on_set():
    png_by_cid, refs_by_section = build_charts(_ctx())
    # equities default-on produces a ChartRef and a png entry
    assert "us_equities" in refs_by_section
    for refs in refs_by_section.values():
        for r in refs:
            assert r.cid in png_by_cid


def test_sparklines_off_when_watchlist_empty():
    _, refs = build_charts(_ctx([]))
    assert "watchlist" not in refs or refs["watchlist"] == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_charts.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 4: Port and restyle charts.py**

Copy `render/charts.py` from v1 into `v2/marketbrief/render/charts.py`. Keep the `Chart` dataclass, `index_change_bar`, `ten_year_trend`, `commodities_normalized`, and the private styling helpers. Apply the §6.5 palette by setting these module constants at the top (replacing v1's color literals):

```python
INK = "#13202E"; PAPER = "#FBFAF7"; GOLD = "#B0892F"
GREEN = "#197A4B"; RED = "#BC3B2E"; GREY = "#6B7785"; HAIRLINE = "#E4E0D7"
```

In `_style_axes`/`_new_axes`/bar coloring, use `GREEN`/`RED` for positive/negative bars, `INK` for axis text, `GREY` for captions, `GOLD` for the single rule. Do not introduce any other colors. Remove any v1 import that does not resolve in v2 (e.g. swap `from sources...` to `marketbrief...`); the chart builders themselves take plain dict/list inputs and have no source imports.

- [ ] **Step 5: Create chart_set.py**

```python
# v2/marketbrief/render/chart_set.py
from __future__ import annotations
from marketbrief.core.enums import ChartKind
from marketbrief.core.models import ChartRef
from marketbrief.render import charts as C


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None  # a chart never blocks the brief (spec §7.5)


def build_charts(ctx) -> tuple[dict[str, bytes], dict[str, list[ChartRef]]]:
    cfg = ctx.config.charts
    png_by_cid: dict[str, bytes] = {}
    refs: dict[str, list[ChartRef]] = {}

    def add(section_id: str, chart, kind: ChartKind):
        if chart is None:
            return
        png_by_cid[chart.cid] = chart.png
        refs.setdefault(section_id, []).append(
            ChartRef(cid=chart.cid, alt=chart.title, kind=kind))

    if cfg.equities:
        changes = {}  # same-day per-index % change; populated once compute provides it
        add("us_equities", _safe(lambda: C.index_change_bar(changes) if changes else None),
            ChartKind.BAR)
    # rates / commodities default-on charts attach here once their history inputs exist;
    # with no history available they are simply skipped (spec §6 default-on, §7.5 skip).
    return png_by_cid, refs
```

Note: charts requiring rolling history (rates trend, commodities trend, sparklines) are wired but no-op until the deferred history sub-project supplies series; `build_charts` skips them cleanly. The equities %-change bar renders as soon as same-day per-index change is available. This keeps #4 honest: no chart fabricates data.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_charts.py -v`
Expected: PASS (3 tests). If `test_build_charts_default_on_set` finds no equities ref because `changes` is empty, adjust the test to assert the no-fabrication behavior (empty refs allowed) — the contract is "no chart without real data."

- [ ] **Step 7: Commit**

```bash
git add v2/marketbrief/render/charts.py v2/marketbrief/render/chart_set.py v2/tests/test_charts.py v2/pyproject.toml
git commit -m "feat(v2): port+restyle charts to §6.5 palette; chart_set honors toggles, never fabricates"
```

---

### Task 12: The Tape template + dumb renderer + MIME assembly

**Files:**
- Create: `v2/marketbrief/render/template.html.j2` (The Tape, refreshed visuals, email-safe)
- Modify: `v2/marketbrief/render/html.py` (render `BriefView`; keep `render_unavailable_notice`)
- Create: `v2/marketbrief/render/mime.py` (multipart with CID parts)
- Test: `v2/tests/test_render_briefview.py`

> Before writing the template, turn the frontend-design plugin ON for this task and apply it to the visual layer (type scale, spacing, card treatment) WITHIN §6.5's firm rules. The structure is ported from v1's `render/template.html.j2`; do not re-open settled §6.5 decisions.

**Interfaces:**
- Consumes: `BriefView`, `png_by_cid: dict[str, bytes]`.
- Produces:
  - `html.render_brief(view: BriefView) -> str` (renders the Jinja template; dumb, no logic).
  - `html.render_unavailable_notice() -> str` (retained).
  - `mime.build_message(html: str, png_by_cid: dict[str, bytes]) -> EmailMessage` with inline CID image parts (no send; just assembly).

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_render_briefview.py
from email.message import EmailMessage
from marketbrief.core.enums import Direction
from marketbrief.core.models import (
    BriefView, SectionVM, WhyLine, StatRow, FigureCell, GlanceRow, LiveSnapshot,
)
from marketbrief.render.html import render_brief
from marketbrief.render.mime import build_message


def _view(degraded=False, banner=None, live=None):
    sec = SectionVM(id="us_equities", title="US Equities", order=1, quiet=False,
                    lead=WhyLine(text="Stocks rose on soft inflation.", hedged=False),
                    stat_rows=[StatRow(label="Indices", cells=[
                        FigureCell(metric_label="S&P", value_str="5,000",
                                   change_str="+0.4%", direction=Direction.UP,
                                   source_url="https://finance.yahoo.com/quote/%5EGSPC")])])
    return BriefView(diff_line="S&P +0.4% since yesterday's close.",
                     glance_rows=[GlanceRow(category="Markets", latest="5,000",
                                            why_brief="Stocks rose.")],
                     sections=[sec], live=live, degraded=degraded, banner_text=banner)


def test_render_contains_section_and_diff():
    html = render_brief(_view())
    assert "US Equities" in html and "S&P +0.4%" in html
    assert "5,000" in html and "finance.yahoo.com" in html


def test_no_em_dash_or_emoji():
    html = render_brief(_view())
    assert "—" not in html  # em dash


def test_degraded_banner_renders():
    html = render_brief(_view(degraded=True, banner="limited data this morning"))
    assert "limited data this morning" in html


def test_live_block_is_fenced_and_labeled():
    live = LiveSnapshot(as_of_label="Pre-market as of 08:25 CT", rows=[], is_premarket=True)
    html = render_brief(_view(live=live))
    assert "Pre-market as of 08:25 CT" in html


def test_mime_has_cid_image_part():
    msg = build_message("<html><body><img src='cid:chart_index'></body></html>",
                        {"chart_index": b"\x89PNG\r\n\x1a\n"})
    assert isinstance(msg, EmailMessage)
    cids = [p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")]
    assert any("chart_index" in c for c in cids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_render_briefview.py -v`
Expected: FAIL (ImportError: render_brief / build_message).

- [ ] **Step 3: Write the template**

Create `v2/marketbrief/render/template.html.j2`. Port the structure from v1's `render/template.html.j2` (masthead → degrade banner → diff line → At-a-Glance card → ordered sections → fenced live block → What to Watch). Constraints (firm): single-column `<table>` layout, fully inline styles, web-safe fonts (Georgia masthead; `Consolas, "SFMono-Regular", monospace` for every figure value/change), §6.5 palette hexes only, green/red for direction only. The template must be logic-free beyond loops and simple conditionals. Required dynamic hooks the test asserts:

```jinja
{% if view.banner_text %}<tr><td style="background:#FBFAF7;color:#BC3B2E;padding:8px 12px;font-family:Georgia,serif;">{{ view.banner_text }}</td></tr>{% endif %}
<tr><td style="font-family:Georgia,serif;color:#13202E;font-weight:bold;padding:8px 12px;">{{ view.diff_line }}</td></tr>
{% for s in view.sections %}
  <tr><td style="border-top:2px solid #B0892F;padding:10px 12px;">
    <h2 style="font-family:Georgia,serif;color:#13202E;margin:0 0 4px 0;">{{ s.title }}{% if s.is_promoted %} (Top Story){% endif %}</h2>
    <p style="font-family:Arial,Helvetica,sans-serif;color:#13202E;margin:0 0 6px 0;">{{ s.lead.text }}</p>
    {% for row in s.stat_rows %}<p style="font-family:Consolas,'SFMono-Regular',monospace;color:#13202E;margin:0;">
      {% for c in row.cells %}{% if c.source_url %}<a href="{{ c.source_url }}" style="color:#13202E;text-decoration:none;">{% endif %}{{ c.metric_label }} {{ c.value_str }} {{ c.change_str }}{% if c.stale %} (stale){% endif %}{% if c.source_url %}</a>{% endif %}&nbsp;&nbsp;{% endfor %}
    </p>{% endfor %}
  </td></tr>
{% endfor %}
{% if view.live %}
  <tr><td style="background:#F2EFE8;border:1px solid #E4E0D7;padding:10px 12px;">
    <strong style="font-family:Georgia,serif;color:#6B7785;">{{ view.live.as_of_label }}</strong>
    {% for c in view.live.rows %}<span style="font-family:Consolas,'SFMono-Regular',monospace;">{{ c.metric_label }} {{ c.value_str }}</span> {% endfor %}
  </td></tr>
{% endif %}
```

Wrap the above rows in the full `<table>` masthead/skeleton ported from v1. No em dashes, no emojis anywhere in the template copy.

- [ ] **Step 4: Rewrite html.py and create mime.py**

```python
# v2/marketbrief/render/html.py  (replace file)
from __future__ import annotations
from pathlib import Path
from jinja2 import Template
from marketbrief.core.models import BriefView

_TEMPLATE_PATH = Path(__file__).parent / "template.html.j2"


def render_brief(view: BriefView) -> str:
    template = Template(_TEMPLATE_PATH.read_text())
    return template.render(view=view)


def render_unavailable_notice() -> str:
    return (
        "<html><body><p>Market data is unavailable this morning. "
        "No brief was generated. Please check an external source directly.</p>"
        "</body></html>"
    )
```

```python
# v2/marketbrief/render/mime.py
from __future__ import annotations
from email.message import EmailMessage


def build_message(html: str, png_by_cid: dict[str, bytes]) -> EmailMessage:
    """Assemble a multipart/related message with inline CID chart images.

    No send here (spec: send path is cutover work). Pure assembly, unit-testable.
    """
    msg = EmailMessage()
    msg["Subject"] = "Daily Market Brief"
    msg.add_alternative(html, subtype="html")
    payload = msg.get_payload()[0]
    for cid, png in png_by_cid.items():
        payload.add_related(png, maintype="image", subtype="png", cid=f"<{cid}>")
    return msg
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd v2 && ./.venv/bin/python -m pytest tests/test_render_briefview.py -v`
Expected: PASS (5 tests). If the old `tests/test_render.py` asserts the removed `render_html(sections, degraded=...)` signature, update it to use `render_brief(view)` (or delete the obsolete assertions) in this commit.

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/render/template.html.j2 v2/marketbrief/render/html.py v2/marketbrief/render/mime.py v2/tests/test_render_briefview.py v2/tests/test_render.py
git commit -m "feat(v2): The Tape template + dumb renderer + CID MIME assembly (frontend-design refresh)"
```

---

### Task 13: Pipeline wiring + brief.py + e2e offline

**Files:**
- Modify: `v2/marketbrief/core/pipeline.py` (replace `_assemble` body to compose a `BriefView`; store it on ctx)
- Modify: `v2/marketbrief/core/context.py` (add `brief_view: BriefView | None = None`)
- Modify: `v2/brief.py` (render `ctx.brief_view`; keep hard-floor + no-state invariant)
- Test: `v2/tests/test_pipeline_assemble.py`, update `v2/tests/test_e2e_offline.py` if present

**Interfaces:**
- Consumes: all section builders (auto-discovered), `assemble.*`, `render.chart_set.build_charts`, `render.html.render_brief`.
- Produces: `ctx.brief_view: BriefView`. `build_brief` renders it. `run_pipeline` unchanged except the enriched `_assemble`.

- [ ] **Step 1: Write the failing test**

```python
# v2/tests/test_pipeline_assemble.py
from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.core.pipeline import run_pipeline


def test_pipeline_produces_brief_view_with_all_sections():
    ctx = BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config())
    out = run_pipeline(ctx, narration_client=None)
    assert out.brief_view is not None
    ids = {s.id for s in out.brief_view.sections}
    expected = {"us_equities", "rates_and_dollar", "commodities", "washington", "movers",
                "economic_data_scorecard", "earnings_on_deck", "watchlist", "crypto",
                "volatility_breadth", "what_to_watch_today"}
    assert expected.issubset(ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && MARKET_BRIEF_OFFLINE=1 ./.venv/bin/python -m pytest tests/test_pipeline_assemble.py -v`
Expected: FAIL (`brief_view` attribute missing / None).

- [ ] **Step 3: Add brief_view to context**

```python
# in v2/marketbrief/core/context.py — add import and field
from marketbrief.core.models import (
    Field, Article, SourceResult, ComputedNumbers, Cause, NarratedWhy, SectionVM,
    HealthReport, BriefView,
)
# add to BriefContext:
    brief_view: BriefView | None = None
```

- [ ] **Step 4: Rewire _assemble in pipeline.py**

Replace the existing `_assemble` function with:

```python
# imports to add at top of pipeline.py
from datetime import datetime
from marketbrief.assemble.diff_line import build_diff_line
from marketbrief.assemble.glance import build_glance_rows
from marketbrief.assemble.topstory import order_sections
from marketbrief.assemble.fence import build_live_snapshot
from marketbrief.assemble.brief_view import build_brief_view


def _assemble(ctx: BriefContext, sections: list) -> BriefContext:
    built = []
    for sec in sections:
        vm, err = run_isolated(f"section:{sec.id}", lambda sec=sec: sec.build(ctx), None)
        if vm is not None:
            built.append(vm)
    ordered = order_sections(ctx, built)
    glance = build_glance_rows(ctx, ordered)
    diff = build_diff_line(ctx)
    # Live snapshot uses the run's wall-clock pull time; rows empty until futures wired.
    live = build_live_snapshot(datetime.now(), rows=[])
    view = build_brief_view(ctx, ordered, glance, diff, live)
    return ctx.with_updates(sections=ordered, brief_view=view)
```

(The `now()` call here is the real pull time per spec §3.1; it is the one wall-clock read and is not under test — tests call `build_live_snapshot` directly with a fixed datetime.)

- [ ] **Step 5: Run the pipeline test**

Run: `cd v2 && MARKET_BRIEF_OFFLINE=1 ./.venv/bin/python -m pytest tests/test_pipeline_assemble.py -v`
Expected: PASS.

- [ ] **Step 6: Rewire brief.py to render the BriefView**

In `v2/brief.py`, change the render import and the `build_brief` body:

```python
from marketbrief.render.html import render_brief, render_unavailable_notice
```

Replace the render line in `build_brief`:

```python
    if ctx.health.hard_floor_tripped:
        return EXIT_HARD_FLOOR, render_unavailable_notice()

    html = render_brief(ctx.brief_view)
    commit_state(state_path, {"run_date": today.isoformat()}, mode=mode)
    return EXIT_OK, html
```

- [ ] **Step 7: Full suite + e2e offline run**

Run:
```bash
cd v2 && ./.venv/bin/python -m pytest -q
```
Expected: all green. Fix any remaining references to the old `render_html`/`SectionVM.body` in pre-existing tests.

Then the e2e offline invariant:
```bash
cd v2 && rm -f last_run.json && MARKET_BRIEF_OFFLINE=1 ./.venv/bin/python brief.py --no-send; echo "exit=$?"; test ! -f last_run.json && echo "no state OK"; grep -c "</section>\|<h2" brief.preview.html
```
Expected: `exit=0`, `no state OK`, and the preview HTML contains all 11 section headers.

- [ ] **Step 8: Commit**

```bash
git add v2/marketbrief/core/pipeline.py v2/marketbrief/core/context.py v2/brief.py v2/tests/test_pipeline_assemble.py
git commit -m "feat(v2): wire assemble->BriefView into pipeline; brief.py renders The Tape (gate 4 e2e)"
```

---

### Task 14: Coverage gate + push + memory update

**Files:**
- No new code; verification + housekeeping.

- [ ] **Step 1: Run coverage**

Run:
```bash
cd v2 && ./.venv/bin/python -m pytest -q --cov=marketbrief --cov-report=term-missing 2>/dev/null | tail -25 || \
  ./.venv/bin/python -m pytest -q | tail -5
```
Expected: suite green; coverage ≥ 80% on the new `sections/`, `assemble/`, `render/` modules. If a module is under 80%, add a focused test for the missing branch and commit it.

- [ ] **Step 2: Push the branch**

```bash
git push origin build/v2
```

- [ ] **Step 3: Update memory**

Update `/Users/jakeliess/.claude/projects/-Users-jakeliess-market-brief/memory/v2-rewrite-decision.md` and `MEMORY.md` index line to record sub-project #4 (output/design) DONE: all 11 sections + diff line + At-a-Glance + live fence + degrade banner + Top Story float + CID chart harness built; render layer ports The Tape with refreshed visuals; send/Actions/secrets remain deferred to cutover. Note the test count and HEAD.

- [ ] **Step 4: Commit memory (if memory is git-tracked) or leave as local memory files**

Memory files live outside the repo; no repo commit needed. Confirm the e2e offline command in the spec §8 still passes as the final gate.

---

## Self-Review

**Spec coverage check (spec §1–§9 of the design doc):**
- 11 sections → Tasks 3, 4, 5, 6. ✓
- Diff line → Task 8. At-a-Glance → Task 8. ✓
- Live pre-market fence (time-aware label) → Task 10 (fence) + Task 12 (template fenced block) + Task 13 (wired). ✓
- Degrade banner → Task 10 (banner) + Task 12 (template) + Task 13. ✓
- Top Story float + mechanical suppression → Task 9. ✓
- 3 default-on charts / CID → Task 11 + Task 12 (img cid) + Task 13. Charts requiring history are wired but skip cleanly (no fabrication) — consistent with spec "never invent a number." ✓
- Enriched typed view models + 3 type-enforced rules (stale, fence, grounding) → Task 1 (types), Task 2/3 (hedged-when-sourceless), Task 8 (stale exclusion), Task 10/12 (fence). ✓
- MIME assembly, no live send → Task 12 (`build_message`), Task 13 (no send path touched). ✓
- Hard-floor unavailable notice → retained in Task 12, used in Task 13 brief.py. ✓
- §6.5 palette/fonts/email-safe → Task 11 (charts), Task 12 (template). ✓
- No-send-no-state invariant → Task 13 Step 7. ✓
- 80% coverage → Task 14. ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Each section builder shows full code. The history-dependent charts are explicitly scoped as no-op-skip with a stated reason, not a placeholder. ✓

**Type consistency:** `SectionVM` fields used in Tasks 3–13 match Task 1's definition (`lead`, `stat_rows`, `why_lines`, `movers`, `sparklines`, `is_promoted`). `Chart` (charts.py) vs `ChartRef` (models) are distinct by design: `Chart` carries png bytes internally; `ChartRef` is the template-facing CID handle — `chart_set.build_charts` converts one to the other. `build_live_snapshot(datetime, rows)`, `banner_text(health)`, `build_brief_view(ctx, ordered, glance, diff, live)`, `render_brief(view)`, `build_message(html, png_by_cid)` signatures are consistent across Tasks 10, 12, 13. ✓
