"""The diff line — "What changed since yesterday" (spec §4.1, §5.5; roadmap §3).

A single highlighted line at the very top of the brief, computed for free from
the cached rolling history. It states only what FLIPPED over the finished day:
direction changes, levels broken, streaks extended, and the one event reframing
things. It is the highest-signal element in the brief.

Pure computation, no network, no model. Consumes the Phase 2 State (rolling
history per metric). Everything here is driven off history, not the calendar, so
a post-holiday gap compares to the last real session (spec §5.5).

Degradation (spec §5.5, roadmap §3.6): if history is missing or too thin to
verify a claim, SKIP that claim rather than printing a wrong delta. If nothing
clears, emit the "quiet tape" line (roadmap §3.7) rather than a manufactured
headline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.metrics import METRICS, METRICS_BY_KEY, is_yield
from engine.state import State

# A streak is only worth printing once it is genuinely a run.
MIN_STREAK = 3
# Need at least this much history to assert a 5-day range claim honestly.
MIN_HISTORY_FOR_RANGE = 5
QUIET_TAPE_LINE = "Quiet tape: no direction changes, broken levels, or streaks since the last session."


@dataclass
class DiffEvent:
    """One observed change, with a priority for selecting the reframing event."""

    metric_key: str
    kind: str            # "flip" | "break_high" | "break_low" | "streak"
    text: str
    priority: int        # higher = more reframing


@dataclass
class DiffResult:
    events: list[DiffEvent] = field(default_factory=list)
    line: str = ""
    quiet: bool = False
    reframing_event: Optional[DiffEvent] = None

    @property
    def has_signal(self) -> bool:
        return bool(self.events)


# --------------------------------------------------------------------------- #
# Per-metric detectors (all history-driven, all degrade to None on thin data)
# --------------------------------------------------------------------------- #
def _direction(delta: float) -> int:
    if delta > 0:
        return 1
    if delta < 0:
        return -1
    return 0


def detect_flip(history: list[float]) -> Optional[str]:
    """Direction change: last session's move sign differs from the prior one.

    Needs three closes (two consecutive deltas). Returns None on thin history,
    so a flip is never asserted from a single data point.
    """
    if len(history) < 3:
        return None
    prev_delta = history[-2] - history[-3]
    last_delta = history[-1] - history[-2]
    pd, ld = _direction(prev_delta), _direction(last_delta)
    if pd == 0 or ld == 0 or pd == ld:
        return None
    return "turned higher" if ld > 0 else "turned lower"


def detect_break(history: list[float], window: int) -> Optional[str]:
    """New N-day high or low set by the latest close.

    Compares the latest close against the prior `window` closes (excluding
    itself). Returns None when history is too short to make the claim honestly.
    """
    if len(history) < window + 1:
        return None
    latest = history[-1]
    prior = history[-(window + 1):-1]
    if latest > max(prior):
        return f"a new {window}-day high"
    if latest < min(prior):
        return f"a new {window}-day low"
    return None


def detect_streak(history: list[float]) -> Optional[tuple[int, str]]:
    """Count consecutive same-direction sessions ending at the latest close.

    Returns (count, direction) only once the run reaches MIN_STREAK, else None.
    """
    if len(history) < MIN_STREAK + 1:
        return None
    deltas = [history[i] - history[i - 1] for i in range(1, len(history))]
    last_dir = _direction(deltas[-1])
    if last_dir == 0:
        return None
    count = 0
    for d in reversed(deltas):
        if _direction(d) == last_dir:
            count += 1
        else:
            break
    if count < MIN_STREAK:
        return None
    return count, ("higher" if last_dir > 0 else "lower")


# --------------------------------------------------------------------------- #
# Assemble
# --------------------------------------------------------------------------- #
def _label(key: str) -> str:
    return METRICS_BY_KEY[key].label


def _ordinal(n: int) -> str:
    # Spelled-as-digits ordinal is whitelisted by the number validator (§5.6).
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def compute_diff(
    state: State,
    *,
    stale_keys: Optional[set[str]] = None,
) -> DiffResult:
    """Build the diff line from cached history.

    Stale metrics are excluded entirely (spec §7.5: stale fields never enter the
    diff line). If history is missing/thin, claims are skipped, not guessed. When
    nothing clears, returns the quiet-tape line.
    """
    stale_keys = stale_keys or set()
    events: list[DiffEvent] = []

    for metric in METRICS:
        key = metric.key
        if key in stale_keys:
            continue
        history = state.history(key)
        if len(history) < 3:
            continue  # too thin for any claim; degrade to silence (spec §5.5)

        label = _label(key)

        flip = detect_flip(history)
        if flip:
            events.append(DiffEvent(key, "flip", f"{label} {flip}", priority=3))

        if len(history) >= MIN_HISTORY_FOR_RANGE:
            # Prefer the wider 20-day break when both fire; it is the bigger story.
            brk20 = detect_break(history, 20)
            brk5 = detect_break(history, 5)
            brk = brk20 or brk5
            if brk:
                kind = "break_high" if "high" in brk else "break_low"
                pr = 4 if "20-day" in brk else 2
                events.append(DiffEvent(key, kind, f"{label} set {brk}", priority=pr))

        streak = detect_streak(history)
        if streak:
            count, direction = streak
            events.append(
                DiffEvent(
                    key,
                    "streak",
                    f"{label} closed {direction} for the {_ordinal(count)} straight session",
                    priority=1,
                )
            )

    if not events:
        return DiffResult(events=[], line=QUIET_TAPE_LINE, quiet=True)

    reframing = max(events, key=lambda e: (e.priority, _abs_move(state, e.metric_key)))
    line = _render_line(events, reframing)
    return DiffResult(events=events, line=line, quiet=False, reframing_event=reframing)


def _abs_move(state: State, key: str) -> float:
    hist = state.history(key)
    if len(hist) < 2:
        return 0.0
    return abs(hist[-1] - hist[-2])


def _render_line(events: list[DiffEvent], reframing: DiffEvent) -> str:
    """Lead with the reframing event, then up to two more, semicolon-joined."""
    ordered = [reframing] + [e for e in events if e is not reframing]
    parts = [e.text for e in ordered[:3]]
    return "; ".join(parts) + "."
