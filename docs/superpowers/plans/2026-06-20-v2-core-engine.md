# Market Brief v2 Core Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the typed, plugin-based core engine for Market Brief v2 — an explicit pipeline over an immutable context, with auto-discovered DataSource and Section plugins, isolated per-plugin failure, and an end-to-end brief that renders offline.

**Architecture:** A frozen Pydantic `BriefContext` threads through ordered stages (`fetch → compute → match → narrate → assemble → render → send`). Two `typing.Protocol`-based registries (DataSource, Section) auto-discover plugins from `v2/marketbrief/sources/` and `v2/marketbrief/sections/`. Every plugin runs inside an isolation guard so one failure degrades only its own output. State writes funnel through one `commit_state()` that is a hard no-op unless `mode == SEND`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Jinja2 (render), PyYAML (config). yfinance/anthropic/matplotlib are wired in later sub-projects; this plan uses only placeholder/offline sources.

## Global Constraints

- Python 3.12. All v2 code lives under `v2/`; do not touch the existing v1 app (`brief.py`, `engine/`, `render/`, `sources/` at repo root).
- Pydantic v2 models for config, facts, view models, and stage I/O. Validate every external input at ingress.
- `--no-send` MUST imply no state write. Every state write funnels through `commit_state()`, a hard no-op when `mode != SEND`.
- Immutability: stages return a NEW `BriefContext` (use `model_copy(update=...)`); never mutate in place. `BriefContext` is `frozen=True`.
- Per-plugin isolation: a `DataSource.fetch()` or `Section.build()` that raises is caught, logged with context, recorded as that plugin's `health = FAILED`, and the run continues. Never silently swallow — always log.
- Professional tone in any user-facing copy: no em dashes, no emojis, plain declarative prose.
- Core fields (ported verbatim from `sources/symbols.py`): `("sp500", "nasdaq", "dow", "russell", "ust10y", "wti", "dxy")`.
- Thresholds (ported verbatim from `config.yaml`): `degraded_stale_threshold: 2`, `hard_floor_missing_threshold: 4`. Hard floor trips when `missing_core > hard_floor_missing_threshold`; degrade trips when `model_failed` OR `stale_core >= degraded_stale_threshold` OR `missing_core >= degraded_stale_threshold`.
- Test seam: `MARKET_BRIEF_OFFLINE=1` makes sources return synthesized clean facts (no network).
- Naming: `camelCase` is NOT used (this is Python) — use `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- Each file <800 lines (target 200-400); functions <50 lines.

---

## File Structure

```
v2/
  brief.py                         # ~100-line orchestrator (Gate 3)
  pyproject.toml                   # deps + pytest config
  marketbrief/
    __init__.py
    core/
      __init__.py
      enums.py                     # RunMode, SourceHealth, Verdict
      models.py                    # Field, SourceResult, ComputedNumbers, Cause, NarratedWhy, SectionVM, HealthReport
      config.py                    # Config (Pydantic), load_config()
      context.py                   # BriefContext (frozen)
      protocols.py                 # DataSource, Section, Validator Protocols
      isolation.py                 # run_isolated() guard
      registry.py                  # discover_sources(), discover_sections()
      health.py                    # assess() -> HealthReport
      state.py                     # load_state(), commit_state() (no-op unless SEND)
      pipeline.py                  # run_pipeline(): ordered stages
    sources/
      __init__.py
      placeholder.py               # one offline DataSource proving the seam
    sections/
      __init__.py
      summary.py                   # one Section proving the seam
    narrate/
      __init__.py
      chain.py                     # ValidatorChain + tag-only cause check
    render/
      __init__.py
      html.py                      # minimal Jinja2 render of SectionVMs
  tests/
    __init__.py
    test_invariants.py             # Gate 1
    test_isolation.py              # Gate 1
    test_health.py                 # Gate 1
    test_registry.py               # Gate 2
    test_pipeline.py               # Gate 2
    test_validator_chain.py        # Gate 2
    test_end_to_end.py             # Gate 3
    conftest.py                    # shared fixtures
```

---

# GATE 1 — Invariants and contracts green

Goal of this gate: the load-bearing safety properties pass as tests before any feature code exists. Stop here for review.

## Task 1: Project scaffold + enums

**Files:**
- Create: `v2/pyproject.toml`, `v2/marketbrief/__init__.py`, `v2/marketbrief/core/__init__.py`, `v2/marketbrief/core/enums.py`, `v2/tests/__init__.py`

**Interfaces:**
- Produces: `RunMode` (`SEND`, `NO_SEND`), `SourceHealth` (`OK`, `STALE`, `FAILED`, `MISSING`), `Verdict` (`PASS`, `HEDGE`, `STRIP`).

- [ ] **Step 1: Write `v2/pyproject.toml`**

```toml
[project]
name = "marketbrief"
version = "2.0.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.6", "PyYAML>=6.0", "Jinja2>=3.1"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Write the enums**

`v2/marketbrief/core/enums.py`:
```python
from __future__ import annotations
from enum import Enum


class RunMode(str, Enum):
    SEND = "send"
    NO_SEND = "no_send"


class SourceHealth(str, Enum):
    OK = "ok"
    STALE = "stale"
    FAILED = "failed"
    MISSING = "missing"


class Verdict(str, Enum):
    PASS = "pass"
    HEDGE = "hedge"
    STRIP = "strip"
```

- [ ] **Step 3: Create the empty `__init__.py` files** listed under Files.

- [ ] **Step 4: Verify import works**

Run: `cd v2 && python -c "from marketbrief.core.enums import RunMode, SourceHealth, Verdict; print(RunMode.SEND, Verdict.STRIP)"`
Expected: `RunMode.SEND Verdict.STRIP`

- [ ] **Step 5: Commit**

```bash
git add v2/pyproject.toml v2/marketbrief v2/tests/__init__.py
git commit -m "feat(v2): scaffold core package + enums"
```

## Task 2: Core Pydantic models

**Files:**
- Create: `v2/marketbrief/core/models.py`
- Test: `v2/tests/test_models.py`

**Interfaces:**
- Consumes: `SourceHealth`, `Verdict` from `enums`.
- Produces:
  - `Field(metric: str, value: float | None, source: str, stale: bool = False, as_of: str | None = None, note: str | None = None)` with properties `is_missing -> bool`, `is_usable -> bool`.
  - `SourceResult(name: str, fields: dict[str, Field], health: SourceHealth, error: str | None = None)`.
  - `ComputedNumbers(values: dict[str, float] = {}, diff_lines: list[str] = [])`.
  - `Cause(claim: str, cause_source_id: str | None, verdict: Verdict = Verdict.PASS)`.
  - `NarratedWhy(section_id: str, text: str, causes: list[Cause] = [], degraded: bool = False)`.
  - `SectionVM(id: str, title: str, order: int, body: str, quiet: bool = False)`.
  - `HealthReport(missing_core: list[str], stale_core: list[str], degraded: bool, hard_floor_tripped: bool)`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_models.py`:
```python
from marketbrief.core.models import Field
from marketbrief.core.enums import SourceHealth


def test_field_missing_when_value_none():
    f = Field(metric="sp500", value=None, source="missing")
    assert f.is_missing is True
    assert f.is_usable is False


def test_field_usable_when_present_and_fresh():
    f = Field(metric="sp500", value=5000.0, source="yfinance")
    assert f.is_missing is False
    assert f.is_usable is True


def test_field_not_usable_when_stale():
    f = Field(metric="sp500", value=5000.0, source="yfinance", stale=True)
    assert f.is_usable is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'marketbrief.core.models'`

- [ ] **Step 3: Write the models**

`v2/marketbrief/core/models.py`:
```python
from __future__ import annotations
from pydantic import BaseModel, Field as PField
from marketbrief.core.enums import SourceHealth, Verdict


class Field(BaseModel):
    metric: str
    value: float | None
    source: str
    stale: bool = False
    as_of: str | None = None
    note: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.value is None or self.source == "missing"

    @property
    def is_usable(self) -> bool:
        return (not self.is_missing) and (not self.stale)


class SourceResult(BaseModel):
    name: str
    fields: dict[str, Field] = PField(default_factory=dict)
    health: SourceHealth = SourceHealth.OK
    error: str | None = None


class ComputedNumbers(BaseModel):
    values: dict[str, float] = PField(default_factory=dict)
    diff_lines: list[str] = PField(default_factory=list)


class Cause(BaseModel):
    claim: str
    cause_source_id: str | None = None
    verdict: Verdict = Verdict.PASS


class NarratedWhy(BaseModel):
    section_id: str
    text: str
    causes: list[Cause] = PField(default_factory=list)
    degraded: bool = False


class SectionVM(BaseModel):
    id: str
    title: str
    order: int
    body: str
    quiet: bool = False


class HealthReport(BaseModel):
    missing_core: list[str] = PField(default_factory=list)
    stale_core: list[str] = PField(default_factory=list)
    degraded: bool = False
    hard_floor_tripped: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/models.py v2/tests/test_models.py
git commit -m "feat(v2): core Pydantic models with Field usability rules"
```

## Task 3: Health assessment (ported thresholds)

**Files:**
- Create: `v2/marketbrief/core/health.py`
- Test: `v2/tests/test_health.py`

**Interfaces:**
- Consumes: `Field`, `HealthReport` from `models`.
- Produces:
  - `CORE_FIELDS: tuple[str, ...] = ("sp500", "nasdaq", "dow", "russell", "ust10y", "wti", "dxy")`.
  - `assess(fields: dict[str, Field], *, degraded_stale_threshold: int, hard_floor_missing_threshold: int, model_failed: bool = False) -> HealthReport`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_health.py`:
```python
from marketbrief.core.health import assess, CORE_FIELDS
from marketbrief.core.models import Field


def _all_ok() -> dict[str, Field]:
    return {k: Field(metric=k, value=1.0, source="yfinance") for k in CORE_FIELDS}


def test_clean_data_no_degrade_no_floor():
    report = assess(_all_ok(), degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.degraded is False
    assert report.hard_floor_tripped is False


def test_two_stale_core_trips_degrade():
    fields = _all_ok()
    fields["sp500"] = Field(metric="sp500", value=1.0, source="yfinance", stale=True)
    fields["wti"] = Field(metric="wti", value=1.0, source="yfinance", stale=True)
    report = assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.degraded is True
    assert report.hard_floor_tripped is False


def test_five_missing_core_trips_hard_floor():
    fields = _all_ok()
    for k in ("sp500", "nasdaq", "dow", "russell", "ust10y"):
        fields[k] = Field(metric=k, value=None, source="missing")
    report = assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.hard_floor_tripped is True


def test_model_failure_alone_trips_degrade():
    report = assess(_all_ok(), degraded_stale_threshold=2, hard_floor_missing_threshold=4, model_failed=True)
    assert report.degraded is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/core/health.py`:
```python
from __future__ import annotations
import math
from marketbrief.core.models import Field, HealthReport

CORE_FIELDS: tuple[str, ...] = ("sp500", "nasdaq", "dow", "russell", "ust10y", "wti", "dxy")


def _is_numeric(value: float | None) -> bool:
    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(f)


def assess(
    fields: dict[str, Field],
    *,
    degraded_stale_threshold: int,
    hard_floor_missing_threshold: int,
    model_failed: bool = False,
) -> HealthReport:
    missing_core: list[str] = []
    stale_core: list[str] = []
    for key in CORE_FIELDS:
        field = fields.get(key)
        if field is None or field.is_missing or not _is_numeric(field.value):
            missing_core.append(key)
        elif field.stale:
            stale_core.append(key)

    hard_floor_tripped = len(missing_core) > hard_floor_missing_threshold
    degraded = (
        model_failed
        or len(stale_core) >= degraded_stale_threshold
        or len(missing_core) >= degraded_stale_threshold
    )
    return HealthReport(
        missing_core=missing_core,
        stale_core=stale_core,
        degraded=degraded,
        hard_floor_tripped=hard_floor_tripped,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_health.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/health.py v2/tests/test_health.py
git commit -m "feat(v2): health assessment with ported thresholds + core fields"
```

## Task 4: Config loader

**Files:**
- Create: `v2/marketbrief/core/config.py`
- Test: `v2/tests/test_config.py`

**Interfaces:**
- Produces:
  - `ResilienceConfig(degraded_stale_threshold: int = 2, hard_floor_missing_threshold: int = 4)`.
  - `Config(resilience: ResilienceConfig, watchlist: list[str] = [])`.
  - `load_config(path: str | Path) -> Config` — reads YAML, validates into `Config`; raises `ValueError` with a clear message on malformed YAML.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_config.py`:
```python
import textwrap
from pathlib import Path
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
    import pytest
    with pytest.raises(ValueError):
        load_config(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/core/config.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/config.py v2/tests/test_config.py
git commit -m "feat(v2): typed config loader with validation"
```

## Task 5: State with the load-bearing no-send invariant

**Files:**
- Create: `v2/marketbrief/core/state.py`
- Test: `v2/tests/test_invariants.py`

**Interfaces:**
- Consumes: `RunMode` from `enums`.
- Produces:
  - `load_state(path: str | Path) -> dict` — returns `{}` if file missing, parses JSON otherwise.
  - `commit_state(path: str | Path, payload: dict, *, mode: RunMode) -> bool` — writes JSON and returns `True` ONLY when `mode == RunMode.SEND`; otherwise writes nothing and returns `False`.

- [ ] **Step 1: Write the failing test (the invariant first)**

`v2/tests/test_invariants.py`:
```python
import json
from pathlib import Path
from marketbrief.core.state import load_state, commit_state
from marketbrief.core.enums import RunMode


def test_no_send_writes_no_state(tmp_path: Path):
    p = tmp_path / "last_run.json"
    wrote = commit_state(p, {"x": 1}, mode=RunMode.NO_SEND)
    assert wrote is False
    assert not p.exists()


def test_send_writes_state(tmp_path: Path):
    p = tmp_path / "last_run.json"
    wrote = commit_state(p, {"x": 1}, mode=RunMode.SEND)
    assert wrote is True
    assert json.loads(p.read_text()) == {"x": 1}


def test_no_send_does_not_overwrite_existing_state(tmp_path: Path):
    p = tmp_path / "last_run.json"
    p.write_text(json.dumps({"day": "yesterday"}))
    commit_state(p, {"day": "today"}, mode=RunMode.NO_SEND)
    assert json.loads(p.read_text()) == {"day": "yesterday"}


def test_load_missing_state_returns_empty(tmp_path: Path):
    assert load_state(tmp_path / "nope.json") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_invariants.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/core/state.py`:
```python
from __future__ import annotations
import json
from pathlib import Path
from marketbrief.core.enums import RunMode


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def commit_state(path: str | Path, payload: dict, *, mode: RunMode) -> bool:
    """Write state ONLY on a real send. A hard no-op under NO_SEND.

    This is the single funnel for all state writes (Global Constraint).
    """
    if mode != RunMode.SEND:
        return False
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_invariants.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/state.py v2/tests/test_invariants.py
git commit -m "feat(v2): state load/commit with no-send no-write invariant"
```

## Task 6: Isolation guard

**Files:**
- Create: `v2/marketbrief/core/isolation.py`
- Test: `v2/tests/test_isolation.py`

**Interfaces:**
- Produces:
  - `run_isolated(label: str, fn: Callable[[], T], fallback: T) -> tuple[T, str | None]` — calls `fn()`; on any `Exception`, logs `label` + traceback to stderr and returns `(fallback, error_message)`. On success returns `(result, None)`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_isolation.py`:
```python
from marketbrief.core.isolation import run_isolated


def test_success_returns_result_and_no_error():
    result, err = run_isolated("ok", lambda: 42, fallback=0)
    assert result == 42
    assert err is None


def test_exception_returns_fallback_and_message(capsys):
    def boom():
        raise ValueError("kaboom")
    result, err = run_isolated("boom-source", boom, fallback="FALLBACK")
    assert result == "FALLBACK"
    assert "kaboom" in err
    captured = capsys.readouterr()
    assert "boom-source" in captured.err  # logged, not swallowed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_isolation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/core/isolation.py`:
```python
from __future__ import annotations
import sys
import traceback
from typing import Callable, TypeVar

T = TypeVar("T")


def run_isolated(label: str, fn: Callable[[], T], fallback: T) -> tuple[T, str | None]:
    """Run fn in isolation. On any exception, log with context and return fallback.

    Never silently swallows: the label + traceback go to stderr (Global Constraint).
    """
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 - intentional plugin firewall
        print(f"[isolated:{label}] failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return fallback, str(exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_isolation.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/isolation.py v2/tests/test_isolation.py
git commit -m "feat(v2): isolation guard for plugin firewall"
```

**GATE 1 CHECKPOINT.** Run `cd v2 && pytest -v`. All of: models, health, config, invariants, isolation green. Stop for user review before Gate 2.

---

# GATE 2 — Registries, pipeline, validator chain working

Goal of this gate: plugins are defined as Protocols, auto-discovered, run through the ordered pipeline with isolation, and the narrate validator-chain seam exists. Stop here for review.

## Task 7: Protocols + BriefContext

**Files:**
- Create: `v2/marketbrief/core/protocols.py`, `v2/marketbrief/core/context.py`
- Test: `v2/tests/test_context.py`

**Interfaces:**
- Consumes: all of `models`, `enums`, `Config`.
- Produces:
  - `DataSource` Protocol: `name: str`; `fetch(ctx: "BriefContext") -> SourceResult`.
  - `Section` Protocol: `id: str`; `order: int`; `build(ctx: "BriefContext") -> SectionVM | None`; `is_quiet(ctx: "BriefContext") -> bool`.
  - `Validator` Protocol: `judge(cause: Cause, ctx: "BriefContext") -> Verdict`.
  - `BriefContext(BaseModel, frozen=True)` with fields: `run_date: date`, `mode: RunMode`, `config: Config`, `prev_state: dict`, `facts: dict[str, SourceResult]`, `numbers: ComputedNumbers`, `causes: list[Cause]`, `narration: dict[str, NarratedWhy]`, `sections: list[SectionVM]`, `health: HealthReport`. Method `with_updates(**kwargs) -> BriefContext` wrapping `model_copy(update=kwargs)`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_context.py`:
```python
from datetime import date
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.models import ComputedNumbers


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_context_is_immutable():
    ctx = _ctx()
    import pytest
    with pytest.raises(Exception):
        ctx.mode = RunMode.SEND  # frozen


def test_with_updates_returns_new_context():
    ctx = _ctx()
    nums = ComputedNumbers(values={"sp500": 5000.0})
    new = ctx.with_updates(numbers=nums)
    assert new.numbers.values["sp500"] == 5000.0
    assert ctx.numbers.values == {}  # original untouched
    assert new is not ctx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_context.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write protocols**

`v2/marketbrief/core/protocols.py`:
```python
from __future__ import annotations
from typing import Protocol, TYPE_CHECKING, runtime_checkable
from marketbrief.core.models import SourceResult, SectionVM, Cause
from marketbrief.core.enums import Verdict

if TYPE_CHECKING:
    from marketbrief.core.context import BriefContext


@runtime_checkable
class DataSource(Protocol):
    name: str
    def fetch(self, ctx: "BriefContext") -> SourceResult: ...


@runtime_checkable
class Section(Protocol):
    id: str
    order: int
    def build(self, ctx: "BriefContext") -> SectionVM | None: ...
    def is_quiet(self, ctx: "BriefContext") -> bool: ...


@runtime_checkable
class Validator(Protocol):
    def judge(self, cause: Cause, ctx: "BriefContext") -> Verdict: ...
```

- [ ] **Step 4: Write context**

`v2/marketbrief/core/context.py`:
```python
from __future__ import annotations
from datetime import date
from pydantic import BaseModel, ConfigDict, Field as PField
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.models import (
    SourceResult, ComputedNumbers, Cause, NarratedWhy, SectionVM, HealthReport,
)


class BriefContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_date: date
    mode: RunMode
    config: Config
    prev_state: dict = PField(default_factory=dict)
    facts: dict[str, SourceResult] = PField(default_factory=dict)
    numbers: ComputedNumbers = PField(default_factory=ComputedNumbers)
    causes: list[Cause] = PField(default_factory=list)
    narration: dict[str, NarratedWhy] = PField(default_factory=dict)
    sections: list[SectionVM] = PField(default_factory=list)
    health: HealthReport = PField(default_factory=HealthReport)

    def with_updates(self, **kwargs) -> "BriefContext":
        return self.model_copy(update=kwargs)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_context.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/core/protocols.py v2/marketbrief/core/context.py v2/tests/test_context.py
git commit -m "feat(v2): plugin Protocols + frozen BriefContext"
```

## Task 8: Placeholder source + summary section plugins

**Files:**
- Create: `v2/marketbrief/sources/__init__.py`, `v2/marketbrief/sources/placeholder.py`, `v2/marketbrief/sections/__init__.py`, `v2/marketbrief/sections/summary.py`
- Test: `v2/tests/test_plugins.py`

**Interfaces:**
- Consumes: `DataSource`, `Section` Protocols; `SourceResult`, `SectionVM`, `Field`, `SourceHealth`.
- Produces:
  - `PlaceholderSource` with `name = "placeholder"`, `fetch()` returning a `SourceResult` carrying clean `Field`s for all CORE_FIELDS (value `1.0`, source `"offline"`).
  - `SummarySection` with `id = "summary"`, `order = 0`, `build()` returning a `SectionVM`, `is_quiet()` returning `False`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_plugins.py`:
```python
from datetime import date
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode
from marketbrief.core.protocols import DataSource, Section
from marketbrief.sources.placeholder import PlaceholderSource
from marketbrief.sections.summary import SummarySection
from marketbrief.core.health import CORE_FIELDS


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_placeholder_satisfies_datasource_protocol():
    assert isinstance(PlaceholderSource(), DataSource)


def test_placeholder_returns_all_core_fields():
    result = PlaceholderSource().fetch(_ctx())
    for k in CORE_FIELDS:
        assert k in result.fields
        assert result.fields[k].is_usable


def test_summary_satisfies_section_protocol():
    assert isinstance(SummarySection(), Section)


def test_summary_builds_a_vm():
    vm = SummarySection().build(_ctx())
    assert vm is not None
    assert vm.id == "summary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_plugins.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the placeholder source**

`v2/marketbrief/sources/placeholder.py`:
```python
from __future__ import annotations
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.health import CORE_FIELDS


class PlaceholderSource:
    name = "placeholder"

    def fetch(self, ctx) -> SourceResult:
        fields = {k: Field(metric=k, value=1.0, source="offline") for k in CORE_FIELDS}
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
```

- [ ] **Step 4: Write the summary section**

`v2/marketbrief/sections/summary.py`:
```python
from __future__ import annotations
from marketbrief.core.models import SectionVM


class SummarySection:
    id = "summary"
    order = 0

    def build(self, ctx) -> SectionVM | None:
        n = len(ctx.facts)
        return SectionVM(
            id=self.id,
            title="At a Glance",
            order=self.order,
            body=f"Brief assembled from {n} source(s).",
            quiet=self.is_quiet(ctx),
        )

    def is_quiet(self, ctx) -> bool:
        return False
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_plugins.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add v2/marketbrief/sources v2/marketbrief/sections v2/tests/test_plugins.py
git commit -m "feat(v2): placeholder source + summary section proving the Protocols"
```

## Task 9: Auto-discovery registries

**Files:**
- Create: `v2/marketbrief/core/registry.py`
- Test: `v2/tests/test_registry.py`

**Interfaces:**
- Consumes: `DataSource`, `Section` Protocols.
- Produces:
  - `discover_sources() -> list[DataSource]` — imports every module in `marketbrief.sources`, instantiates each class that satisfies the `DataSource` Protocol.
  - `discover_sections() -> list[Section]` — same for `marketbrief.sections`, sorted by `order`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_registry.py`:
```python
from marketbrief.core.registry import discover_sources, discover_sections


def test_discovers_placeholder_source():
    names = [s.name for s in discover_sources()]
    assert "placeholder" in names


def test_discovers_summary_section():
    ids = [s.id for s in discover_sections()]
    assert "summary" in ids


def test_sections_sorted_by_order():
    sections = discover_sections()
    orders = [s.order for s in sections]
    assert orders == sorted(orders)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/core/registry.py`:
```python
from __future__ import annotations
import importlib
import inspect
import pkgutil
from marketbrief.core.protocols import DataSource, Section
import marketbrief.sources as sources_pkg
import marketbrief.sections as sections_pkg


def _instantiate_matching(package, protocol) -> list:
    found = []
    for mod_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{mod_info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue  # skip imported classes, only those defined here
            instance = obj()
            if isinstance(instance, protocol):
                found.append(instance)
    return found


def discover_sources() -> list[DataSource]:
    return _instantiate_matching(sources_pkg, DataSource)


def discover_sections() -> list[Section]:
    sections = _instantiate_matching(sections_pkg, Section)
    return sorted(sections, key=lambda s: s.order)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_registry.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/registry.py v2/tests/test_registry.py
git commit -m "feat(v2): auto-discovery registries for sources + sections"
```

## Task 10: Validator chain (the "why" seam) + tag-only cause check

**Files:**
- Create: `v2/marketbrief/narrate/__init__.py`, `v2/marketbrief/narrate/chain.py`
- Test: `v2/tests/test_validator_chain.py`

**Interfaces:**
- Consumes: `Validator` Protocol, `Cause`, `Verdict`, `BriefContext`.
- Produces:
  - `_CAUSAL_RE` regex (ported verbatim from `engine/matcher.py`).
  - `TagOnlyCauseCheck` Validator: `judge()` returns `Verdict.STRIP` when the claim has a causal verb but `cause_source_id is None`, else `Verdict.PASS`.
  - `run_chain(cause: Cause, ctx: BriefContext, validators: list[Validator]) -> Cause` — applies validators in order; the strongest verdict wins (`STRIP` > `HEDGE` > `PASS`); returns a NEW `Cause` with the resolved `verdict`. A validator that raises is treated as `STRIP` (fail-closed) and logged via `run_isolated`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_validator_chain.py`:
```python
from datetime import date
from marketbrief.narrate.chain import TagOnlyCauseCheck, run_chain
from marketbrief.core.models import Cause
from marketbrief.core.enums import Verdict
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_tag_only_strips_uncited_causal_claim():
    cause = Cause(claim="Stocks fell because of weak data", cause_source_id=None)
    out = run_chain(cause, _ctx(), [TagOnlyCauseCheck()])
    assert out.verdict == Verdict.STRIP


def test_tag_only_passes_cited_causal_claim():
    cause = Cause(claim="Stocks fell because of weak data", cause_source_id="art-1")
    out = run_chain(cause, _ctx(), [TagOnlyCauseCheck()])
    assert out.verdict == Verdict.PASS


def test_strongest_verdict_wins():
    class Hedger:
        def judge(self, cause, ctx): return Verdict.HEDGE
    class Stripper:
        def judge(self, cause, ctx): return Verdict.STRIP
    cause = Cause(claim="no causal verb here", cause_source_id="art-1")
    out = run_chain(cause, _ctx(), [Hedger(), Stripper()])
    assert out.verdict == Verdict.STRIP


def test_throwing_validator_fails_closed_to_strip():
    class Boom:
        def judge(self, cause, ctx): raise RuntimeError("bad")
    cause = Cause(claim="anything", cause_source_id="art-1")
    out = run_chain(cause, _ctx(), [Boom()])
    assert out.verdict == Verdict.STRIP
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_validator_chain.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/narrate/chain.py`:
```python
from __future__ import annotations
import re
from marketbrief.core.models import Cause
from marketbrief.core.enums import Verdict
from marketbrief.core.context import BriefContext
from marketbrief.core.protocols import Validator
from marketbrief.core.isolation import run_isolated

# Ported verbatim from engine/matcher.py
_CAUSAL_RE = re.compile(
    r"\b(because|due to|on (?:soft|strong|weak|robust|the)|amid|after|as|driven by|"
    r"thanks to|owing to|spurred by|fueled by|on the back of)\b",
    re.IGNORECASE,
)

_RANK = {Verdict.PASS: 0, Verdict.HEDGE: 1, Verdict.STRIP: 2}


class TagOnlyCauseCheck:
    """A causal verb requires a non-null cause_source_id (ported §5.6 cause check)."""

    def judge(self, cause: Cause, ctx: BriefContext) -> Verdict:
        has_causal = bool(_CAUSAL_RE.search(cause.claim))
        if has_causal and not cause.cause_source_id:
            return Verdict.STRIP
        return Verdict.PASS


def run_chain(cause: Cause, ctx: BriefContext, validators: list[Validator]) -> Cause:
    worst = Verdict.PASS
    for v in validators:
        verdict, err = run_isolated(
            f"validator:{type(v).__name__}", lambda v=v: v.judge(cause, ctx), Verdict.STRIP
        )
        if _RANK[verdict] > _RANK[worst]:
            worst = verdict
    return cause.model_copy(update={"verdict": worst})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_validator_chain.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/narrate v2/tests/test_validator_chain.py
git commit -m "feat(v2): validator chain seam + ported tag-only cause check"
```

## Task 11: The pipeline runner

**Files:**
- Create: `v2/marketbrief/core/pipeline.py`
- Test: `v2/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `discover_sources`, `discover_sections`, `run_isolated`, `assess`, `BriefContext`, `SourceResult`, `SourceHealth`.
- Produces:
  - `run_pipeline(ctx: BriefContext, *, sources: list | None = None, sections: list | None = None) -> BriefContext` — runs stages in order: fetch (each source isolated; a failure records a `SourceResult(health=FAILED)`), assess health into `ctx.health`, assemble (each section isolated; `None` or quiet handled), returning the final context. (compute/match/narrate are stubbed pass-throughs in this sub-project; sources default to `discover_sources()`, sections to `discover_sections()`.)

- [ ] **Step 1: Write the failing test**

`v2/tests/test_pipeline.py`:
```python
from datetime import date
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.context import BriefContext
from marketbrief.core.config import Config
from marketbrief.core.enums import RunMode, SourceHealth
from marketbrief.core.models import SourceResult


def _ctx() -> BriefContext:
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND, config=Config(), prev_state={})


def test_pipeline_fetches_and_assembles():
    out = run_pipeline(_ctx())
    assert "placeholder" in out.facts
    assert any(s.id == "summary" for s in out.sections)
    assert out.health.hard_floor_tripped is False


def test_failing_source_is_isolated():
    class BoomSource:
        name = "boom"
        def fetch(self, ctx): raise RuntimeError("network down")
    out = run_pipeline(_ctx(), sources=[BoomSource()], sections=[])
    assert out.facts["boom"].health == SourceHealth.FAILED
    # brief still produced a context, did not crash
    assert isinstance(out, BriefContext)


def test_failing_section_is_isolated():
    class BoomSection:
        id = "boom"; order = 1
        def build(self, ctx): raise RuntimeError("render error")
        def is_quiet(self, ctx): return False
    out = run_pipeline(_ctx(), sections=[BoomSection()])
    # boom section dropped, but pipeline finished
    assert all(s.id != "boom" for s in out.sections)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/core/pipeline.py`:
```python
from __future__ import annotations
from marketbrief.core.context import BriefContext
from marketbrief.core.models import SourceResult
from marketbrief.core.enums import SourceHealth
from marketbrief.core.isolation import run_isolated
from marketbrief.core.registry import discover_sources, discover_sections
from marketbrief.core.health import assess


def _fetch(ctx: BriefContext, sources: list) -> BriefContext:
    facts: dict[str, SourceResult] = {}
    for src in sources:
        fallback = SourceResult(name=src.name, health=SourceHealth.FAILED)
        result, err = run_isolated(f"source:{src.name}", lambda src=src: src.fetch(ctx), fallback)
        if err is not None:
            result = SourceResult(name=src.name, health=SourceHealth.FAILED, error=err)
        facts[src.name] = result
    return ctx.with_updates(facts=facts)


def _assess(ctx: BriefContext) -> BriefContext:
    merged = {}
    for result in ctx.facts.values():
        merged.update(result.fields)
    report = assess(
        merged,
        degraded_stale_threshold=ctx.config.resilience.degraded_stale_threshold,
        hard_floor_missing_threshold=ctx.config.resilience.hard_floor_missing_threshold,
    )
    return ctx.with_updates(health=report)


def _assemble(ctx: BriefContext, sections: list) -> BriefContext:
    built = []
    for sec in sections:
        vm, err = run_isolated(f"section:{sec.id}", lambda sec=sec: sec.build(ctx), None)
        if vm is not None:
            built.append(vm)
    return ctx.with_updates(sections=sorted(built, key=lambda v: v.order))


def run_pipeline(ctx: BriefContext, *, sources: list | None = None, sections: list | None = None) -> BriefContext:
    sources = discover_sources() if sources is None else sources
    sections = discover_sections() if sections is None else sections
    ctx = _fetch(ctx, sources)
    ctx = _assess(ctx)
    # compute / match / narrate are pass-through stubs in this sub-project
    ctx = _assemble(ctx, sections)
    return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_pipeline.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/core/pipeline.py v2/tests/test_pipeline.py
git commit -m "feat(v2): ordered pipeline runner with per-stage isolation"
```

**GATE 2 CHECKPOINT.** Run `cd v2 && pytest -v`. Registries, context, plugins, validator chain, pipeline all green. Stop for user review before Gate 3.

---

# GATE 3 — End-to-end brief renders offline

Goal of this gate: `python v2/brief.py --no-send` produces an HTML brief from the registries, writes NO state, and the hard-floor path works.

## Task 12: Minimal HTML renderer

**Files:**
- Create: `v2/marketbrief/render/__init__.py`, `v2/marketbrief/render/html.py`
- Test: `v2/tests/test_render.py`

**Interfaces:**
- Consumes: `SectionVM`, `HealthReport`.
- Produces:
  - `render_html(sections: list[SectionVM], *, degraded: bool) -> str` — Jinja2 string template rendering an ordered list of sections; includes a degrade banner when `degraded` is True. No em dashes, no emojis.
  - `render_unavailable_notice() -> str` — the hard-floor "data unavailable" HTML.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_render.py`:
```python
from marketbrief.render.html import render_html, render_unavailable_notice
from marketbrief.core.models import SectionVM


def test_renders_sections_in_order():
    vms = [SectionVM(id="a", title="Alpha", order=1, body="aaa"),
           SectionVM(id="b", title="Beta", order=0, body="bbb")]
    html = render_html(vms, degraded=False)
    assert "Alpha" in html and "Beta" in html
    assert html.index("Beta") < html.index("Alpha")  # order respected by caller


def test_degrade_banner_appears():
    html = render_html([], degraded=True)
    assert "degraded" in html.lower() or "limited data" in html.lower()


def test_unavailable_notice_has_no_emoji_or_emdash():
    html = render_unavailable_notice()
    assert "—" not in html  # no em dash
    assert "data" in html.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`v2/marketbrief/render/html.py`:
```python
from __future__ import annotations
from jinja2 import Template
from marketbrief.core.models import SectionVM

_TEMPLATE = Template(
    """<html><body>
{% if degraded %}<p class="banner">Some data was limited or could not be refreshed this morning.</p>{% endif %}
{% for s in sections %}<section><h2>{{ s.title }}</h2><p>{{ s.body }}</p></section>
{% endfor %}</body></html>"""
)


def render_html(sections: list[SectionVM], *, degraded: bool) -> str:
    ordered = sorted(sections, key=lambda v: v.order)
    return _TEMPLATE.render(sections=ordered, degraded=degraded)


def render_unavailable_notice() -> str:
    return (
        "<html><body><p>Market data is unavailable this morning. "
        "No brief was generated. Please check an external source directly.</p>"
        "</body></html>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_render.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add v2/marketbrief/render v2/tests/test_render.py
git commit -m "feat(v2): minimal HTML renderer + unavailable notice"
```

## Task 13: Orchestrator + end-to-end test

**Files:**
- Create: `v2/brief.py`
- Test: `v2/tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `build_brief(*, mode: RunMode, config_path, state_path, today=None) -> tuple[int, str]` — returns `(exit_code, html)`. Runs the pipeline; on `hard_floor_tripped` returns `(2, unavailable_notice)` and does NOT write state; else renders the brief, calls `commit_state(...)` (a no-op under NO_SEND), returns `(0, html)`.
  - `main(argv) -> int` — argparse with `--no-send`; default mode is SEND.
- Constants: `EXIT_OK = 0`, `EXIT_HARD_FLOOR = 2`.

- [ ] **Step 1: Write the failing test**

`v2/tests/test_end_to_end.py`:
```python
from datetime import date
from pathlib import Path
from marketbrief.core.enums import RunMode
import brief


def _cfg(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text("resilience:\n  degraded_stale_threshold: 2\n  hard_floor_missing_threshold: 4\nwatchlist: []\n")
    return p


def test_no_send_builds_brief_and_writes_no_state(tmp_path: Path):
    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.NO_SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert "At a Glance" in html
    assert not state.exists()  # the load-bearing invariant, end to end


def test_send_writes_state(tmp_path: Path):
    state = tmp_path / "last_run.json"
    code, html = brief.build_brief(
        mode=RunMode.SEND, config_path=_cfg(tmp_path), state_path=state, today=date(2026, 6, 20)
    )
    assert code == 0
    assert state.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd v2 && pytest tests/test_end_to_end.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brief'`

- [ ] **Step 3: Write the orchestrator**

`v2/brief.py`:
```python
from __future__ import annotations
import argparse
import sys
from datetime import date
from pathlib import Path
from marketbrief.core.enums import RunMode
from marketbrief.core.config import load_config
from marketbrief.core.context import BriefContext
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.state import load_state, commit_state
from marketbrief.render.html import render_html, render_unavailable_notice

EXIT_OK = 0
EXIT_HARD_FLOOR = 2


def build_brief(*, mode: RunMode, config_path, state_path, today: date | None = None) -> tuple[int, str]:
    today = today or date.today()
    config = load_config(config_path)
    prev_state = load_state(state_path)
    ctx = BriefContext(run_date=today, mode=mode, config=config, prev_state=prev_state)
    ctx = run_pipeline(ctx)

    if ctx.health.hard_floor_tripped:
        return EXIT_HARD_FLOOR, render_unavailable_notice()

    html = render_html(ctx.sections, degraded=ctx.health.degraded)
    commit_state(state_path, {"run_date": today.isoformat()}, mode=mode)
    return EXIT_OK, html


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Market Brief v2")
    parser.add_argument("--no-send", action="store_true", help="build only, no send, no state write")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--state", default="last_run.json")
    args = parser.parse_args(argv)
    mode = RunMode.NO_SEND if args.no_send else RunMode.SEND
    code, html = build_brief(mode=mode, config_path=args.config, state_path=args.state)
    Path("brief.preview.html").write_text(html)
    print(f"mode={mode.value} exit={code} bytes={len(html)}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd v2 && pytest tests/test_end_to_end.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the orchestrator for real (offline)**

Run: `cd v2 && python brief.py --no-send`
Expected: prints `mode=no_send exit=0 bytes=...`; `v2/brief.preview.html` exists; no `last_run.json` written.

- [ ] **Step 6: Full suite green + commit**

Run: `cd v2 && pytest -v`
Expected: all tasks' tests pass.

```bash
git add v2/brief.py v2/tests/test_end_to_end.py
git commit -m "feat(v2): orchestrator + end-to-end offline brief (Gate 3)"
```

**GATE 3 CHECKPOINT.** `python v2/brief.py --no-send` renders a brief offline, writes no state, hard-floor path returns exit 2. Stop for user review. Sub-project #1 complete; next is the sub-project #2 (data layer) spec.

---

## Self-Review

**1. Spec coverage:**
- §1 pipeline + two registries -> Tasks 7, 9, 11. ✓
- §2 module layout -> all tasks follow the tree. ✓
- §3 BriefContext immutable flow -> Task 7 (frozen + with_updates). ✓
- §3.1 validator chain seam + tag-only check -> Task 10. ✓
- §4 per-plugin isolation -> Task 6 + Tasks 11 (used in fetch/assemble). ✓
- §4 hard floor + degrade gates -> Task 3 (assess) + Task 13 (orchestrator branch). ✓
- §4 no-send no-state invariant -> Task 5 + Task 13 end-to-end assertion. ✓
- §4 validation at boundaries -> Task 4 (config), Task 2 (Pydantic models). ✓
- §5 testing order (invariants first, contract via Protocol isinstance, units, integration) -> Gates 1/2/3. ✓
- Done-when bars -> Task 13 step 5 (offline run), full suite, ~100-line orchestrator (brief.py is ~45 lines). ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; no "add error handling" hand-waves (isolation guard is concrete). ✓

**3. Type consistency:** `BriefContext.with_updates`, `SourceResult(name, fields, health, error)`, `run_isolated(label, fn, fallback) -> (T, str|None)`, `run_chain(cause, ctx, validators) -> Cause`, `assess(...)` signature, `CORE_FIELDS` tuple — all referenced consistently across tasks. Verdict ranking (`PASS<HEDGE<STRIP`) consistent in Task 10. ✓

**Note on compute/match/narrate:** these stages are deliberately pass-through stubs in this sub-project (the spec scopes real compute/matching/narration to sub-projects #2 and #3). The pipeline structure reserves their slots; the validator chain is fully built so #3 only appends an entailment validator.
