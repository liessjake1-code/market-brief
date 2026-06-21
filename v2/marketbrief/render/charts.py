"""Static PNG charts, embedded inline (CID) so they show even when remote images
are blocked (spec §6; roadmap §7.11).

Three default-on charts: index daily %-change bar, yield curve + 10-year trend,
WTI 1-month trend. Others (VIX, movers, crypto, scorecard, watchlist sparklines)
are gated behind the config `charts` flags. Each builder returns a Chart (a CID +
PNG bytes); the caller (brief.py) decides which to build from config and attaches
the bytes to the email via render/send.py.

Pure: takes already-computed numbers and history lists, does no network and no
state access. matplotlib runs on the headless Agg backend.

§6.5 palette (dark terminal): near-black PAPER background, AMBER (#E8A33D) as the
single chart accent, GREEN/RED for direction only (bars, WTI fill), TEXT off-white
for axis emphasis, MUTED grey for captions and ticks.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # headless: no display, deterministic PNG bytes
import matplotlib.pyplot as plt  # noqa: E402

# §6.5 dark-terminal palette. GOLD (now amber) is the single chart accent.
# GREEN/RED carry direction only (bar up/down, WTI fill). Constant NAMES are kept
# stable (INK/PAPER/GOLD/...) so every reference below remaps by value alone; their
# ROLES now read against a near-black panel: INK is the off-white emphasis text,
# PAPER the near-black background, GREY the muted tick/caption grey.
# Copper leg in commodities_normalized gets a warm tone that stays distinct from
# amber on the dark panel without adding a new palette entry.
INK = "#E6E3DA"        # off-white emphasis (titles, end-value labels)
PAPER = "#0B0E14"      # near-black chart background
HAIRLINE = "#232A36"   # hairline spines / gridlines
GOLD = "#E8A33D"       # amber accent (single brand accent: lines, fills)
GREEN = "#4FB477"      # up direction only
RED = "#E5594F"        # down direction only
GREY = "#7A828F"       # muted ticks, captions, subtitles

FIG_DPI = 110
_CHART_FONT = {"family": "monospace"}


@dataclass(frozen=True)
class Chart:
    """One rendered chart: a stable CID, its PNG bytes, and a text summary.

    `summary` is a one-line, image-free description used as the img alt text so a
    client that blocks images still leaves a readable line (HANDOFF_DESIGN).
    """

    cid: str            # referenced from the template as src="cid:<cid>"
    png: bytes
    title: str = ""
    summary: str = ""


def _style_axes(ax) -> None:
    """Apply the §6.5 palette to one axes (PAPER face, HAIRLINE spines)."""
    ax.set_facecolor(PAPER)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(HAIRLINE)
    ax.tick_params(colors=GREY, labelsize=8)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily("monospace")


def _new_axes(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor(PAPER)
    _style_axes(ax)
    return fig, ax


def _to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=FIG_DPI, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


# A "month" of trading sessions, so trend charts show ~a month rather than the
# whole rolling backfill (which can span a far larger, alarming-looking move).
_MONTH_SESSIONS = 21


def _fmt_date(iso: str) -> str:
    """'2026-05-20' -> 'May 20'. Empty/garbage in -> '' (skipped on the axis)."""
    from datetime import date as _date
    try:
        d = _date.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    return f"{d:%b} {d.day}"


# Minimum gap (in data-point indices) between two dated x-ticks, so their labels
# never crowd into each other ("Jun JuJu 18"). At ~21 points across the panel this
# keeps ticks comfortably apart.
_MIN_TICK_GAP = 4


def _date_xaxis(ax, dates: list[str], n: int) -> str:
    """Label up to 4 well-separated x-ticks with real dates; return a span label.

    `dates` is parallel to the n-point series (most-recent-last); entries may be ''
    for older pre-schema closes. Ticks are chosen evenly across the labelled points
    AND forced at least `_MIN_TICK_GAP` indices apart so adjacent labels never
    overlap. Falls back to clean unlabeled ticks (and an empty span) when no usable
    dates are present, so the axis is never wrong.
    """
    labeled = [(i, _fmt_date(dates[i])) for i in range(n) if i < len(dates) and _fmt_date(dates[i])]
    if not labeled:
        ax.set_xticks([])
        return ""
    # Evenly spaced target positions across the labelled span (first, ~4 ticks, last).
    first_idx, last_idx = labeled[0][0], labeled[-1][0]
    by_idx = dict(labeled)
    targets = [round(first_idx + (last_idx - first_idx) * k / 3) for k in range(4)]
    # Snap each target to the nearest point that actually has a date.
    avail = [i for i, _ in labeled]
    picks: list[int] = []
    for t in targets:
        nearest = min(avail, key=lambda i: abs(i - t))
        # Keep only ticks at least _MIN_TICK_GAP apart so labels never collide.
        if not picks or nearest - picks[-1] >= _MIN_TICK_GAP:
            picks.append(nearest)
    if picks and picks[-1] != last_idx and last_idx - picks[-1] >= _MIN_TICK_GAP:
        picks.append(last_idx)
    ax.set_xticks(picks)
    ax.set_xticklabels([by_idx[i] for i in picks], fontsize=7)
    first_lbl, last_lbl = labeled[0][1], labeled[-1][1]
    return f"{first_lbl} - {last_lbl}" if first_lbl != last_lbl else last_lbl


def _titled(ax, title: str, subtitle: str) -> None:
    """Left-aligned title with a small grey 'what this shows' line beneath it.

    The title is lifted with generous pad so the subtitle (drawn just above the
    axes) sits cleanly under it without overlap.
    """
    ax.set_title(title, color=INK, fontsize=11, family="monospace", loc="left", pad=18)
    if subtitle:
        ax.text(0.0, 1.015, subtitle, transform=ax.transAxes, color=GREY, fontsize=7.5,
                ha="left", va="bottom", family="monospace")


def _pad_ylim(ax, series: list[float], *, min_frac: float = 0.03,
              headroom: float = 2.0) -> None:
    """Pad the y-limits so a small real range is not magnified into a sawtooth.

    A 14 bps move over a month is real but tiny; left to autoscale, matplotlib
    fills the panel and the line reads as random noise. We enforce a minimum
    visible span of `min_frac` of the series level (3% of a 4.4% yield ~ 13 bps
    floor) centered on the data, then multiply by `headroom` so the real wiggle
    occupies only the middle of the panel. A quiet metric then reads as a quiet,
    gently-sloped line instead of a panel-filling sawtooth.
    """
    lo, hi = min(series), max(series)
    mid = (lo + hi) / 2.0
    span = hi - lo
    floor = abs(mid) * min_frac
    half = max(span, floor) / 2.0 * headroom
    ax.set_ylim(mid - half, mid + half)


def index_change_bar(changes: dict[str, float], *, cid: str = "chart_index") -> Optional[Chart]:
    """Daily percent-change bar across the indices (spec §6 default-on).

    `changes` maps a display label -> percent change. Green bars up, red down, so
    rotation reads instantly. Returns None when there is nothing to plot.
    """
    items = [(label, val) for label, val in changes.items() if val is not None]
    if not items:
        return None
    labels = [lbl for lbl, _ in items]
    values = [val for _, val in items]
    colors = [GREEN if v >= 0 else RED for v in values]

    fig, ax = _new_axes(4.8, 2.6)
    bars = ax.bar(labels, values, color=colors, width=0.6)
    ax.axhline(0, color=INK, linewidth=0.8)
    ax.set_ylabel("Daily change (%)", color=GREY, fontsize=8, **_CHART_FONT)
    ax.set_title("Index daily change", color=INK, fontsize=10, **_CHART_FONT)
    for bar, v in zip(bars, values):
        ax.annotate(f"{v:+.1f}%", (bar.get_x() + bar.get_width() / 2, v),
                    ha="center", va="bottom" if v >= 0 else "top",
                    color=INK, fontsize=8)
    summary = "Index daily change: " + ", ".join(f"{lbl} {v:+.1f}%" for lbl, v in items)
    return Chart(cid=cid, png=_to_png(fig), title="Index daily change", summary=summary)


def ten_year_trend(
    *,
    ten_year_history: list[float],
    ten_year_dates: Optional[list[str]] = None,
    cid: str = "chart_rates",
) -> Optional[Chart]:
    """A clean 10-year yield month trend, padded so it is not a sawtooth (redesign).

    One panel only: the 10-year trend over the trailing month, dated x-axis, a
    unit-labeled y-axis, and an annotated end value. The 2s10s spread and DXY now
    read as NUMBERS in the rates stat table, not extra chart lines (the human found
    multi-line rates charts confusing). _pad_ylim keeps a quiet real range from
    being magnified into noise. Returns None on thin history.
    """
    full = [v for v in ten_year_history if v is not None]
    if len(full) < 2:
        return None
    series = full[-_MONTH_SESSIONS:]
    n = len(series)
    win_dates = (ten_year_dates or [])[-len(full):][-n:]

    fig, ax = _new_axes(5.4, 2.7)
    ax.plot(range(n), series, color=GOLD, linewidth=2.0)
    ax.fill_between(range(n), series, min(series) - (max(series) - min(series) or 0.01),
                    color=GOLD, alpha=0.10)
    span = _date_xaxis(ax, win_dates, n)
    _titled(ax, "10-year Treasury yield, past month",
            "Daily close" + (f"  ·  {span}" if span else ""))
    ax.set_ylabel("Yield (%)", color=GREY, fontsize=8, **_CHART_FONT)
    ax.annotate(f"{series[0]:.2f}%", (0, series[0]), textcoords="offset points",
                xytext=(2, 6), ha="left", color=GREY, fontsize=8)
    ax.annotate(f"{series[-1]:.2f}%", (n - 1, series[-1]), textcoords="offset points",
                xytext=(-2, 6), ha="right", color=INK, fontsize=9, fontweight="bold")
    _pad_ylim(ax, series)
    fig.tight_layout()
    bps = (series[-1] - series[0]) * 100.0
    summary = (f"10-year Treasury yield, past month: {series[-1]:.2f}%, "
               f"{'up' if bps >= 0 else 'down'} {abs(bps):.0f} bps from {series[0]:.2f}%")
    return Chart(cid=cid, png=_to_png(fig), title="10-year yield", summary=summary)


# The three commodity legs of the normalized chart: key -> (display label, color).
# WTI uses GOLD/amber (the single §6.5 accent); gold and copper get distinct warm
# tones that read on the dark panel so three lines stay legible. Copper "#C77B4A"
# is a commodity-only exception (this chart requires rolling history — deferred to a
# future sub-project — so it does not appear in #4 output, but the code stays intact).
_COMMODITY_LEGS: tuple[tuple[str, str, str], ...] = (
    ("wti", "WTI crude", GOLD),       # amber, the primary accent
    ("gold", "Gold", "#E8D44D"),      # brighter yellow, distinct from amber on dark
    ("copper", "Copper", "#C77B4A"),  # warm copper, distinct from both
)


def _rebased(series: list[float]) -> Optional[list[float]]:
    """Rebase a clamped series to 100 at its first point. None if unusable."""
    clean = [v for v in series if v is not None]
    window = clean[-_MONTH_SESSIONS:]
    if len(window) < 2 or not window[0]:
        return None
    base = window[0]
    return [v / base * 100.0 for v in window]


def commodities_normalized(
    histories: dict[str, list[float]],
    *,
    dates: Optional[dict[str, list[str]]] = None,
    cid: str = "chart_commodities",
) -> Optional[Chart]:
    """WTI, gold, and copper rebased to 100 ~a month ago — relative performance.

    One normalized chart so the three read as relative moves off a shared base of
    100, not three different price scales (the human's design). Each leg is clamped
    to the trailing ~21 sessions and rebased to its own first point. Returns None
    when no leg can be drawn honestly. The returned summary is a Python-computed,
    accuracy-safe takeaway used as the chart read.
    """
    dates = dates or {}
    fig, ax = _new_axes(5.6, 2.9)
    drawn: list[tuple[str, list[float]]] = []
    span = ""
    for key, label, color in _COMMODITY_LEGS:
        rebased = _rebased(histories.get(key, []))
        if rebased is None:
            continue
        n = len(rebased)
        ax.plot(range(n), rebased, color=color, linewidth=1.9, label=label)
        ax.annotate(f"{rebased[-1]:.0f}", (n - 1, rebased[-1]), textcoords="offset points",
                    xytext=(4, 0), ha="left", va="center", color=color, fontsize=8, fontweight="bold")
        drawn.append((label, rebased))
        if not span:
            full = [v for v in histories.get(key, []) if v is not None]
            win_dates = (dates.get(key, []) or [])[-len(full):][-n:]
            span = _date_xaxis(ax, win_dates, n)

    if not drawn:
        plt.close(fig)
        return None

    ax.axhline(100, color=GREY, linewidth=0.8, linestyle=(0, (3, 3)))
    _titled(ax, "Commodities, rebased to 100 (past month)",
            "Relative performance, daily close" + (f"  ·  {span}" if span else ""))
    ax.set_ylabel("Index (start = 100)", color=GREY, fontsize=8, **_CHART_FONT)
    # Legend BELOW the plot so it never overlaps the rebased lines (which sit near
    # the 100 baseline early on, right where an upper-left legend would land).
    # labelcolor=INK is load-bearing on the dark panel: with frameon=False the
    # near-black PAPER shows through, so the default black label text would be
    # invisible. INK is the off-white emphasis color.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=len(drawn),
              fontsize=7, frameon=False, prop={"family": "monospace"}, labelcolor=INK)
    fig.tight_layout()

    bits = [f"{label} {rebased[-1] - 100.0:+.1f}%" for label, rebased in drawn]
    summary = "Commodities rebased to 100 (past month): " + ", ".join(bits)
    return Chart(cid=cid, png=_to_png(fig), title="Commodities", summary=summary)


# --------------------------------------------------------------------------- #
# Python-computed chart takeaways ("what this tells you") — accuracy-safe (§1).
# Every figure here is computed straight from the data; the model writes none of
# it, so a chart's one-line read can never carry a wrong number.
# --------------------------------------------------------------------------- #
def _range_position(series: list[float]) -> str:
    """Where the latest point sits in the window's range: top / bottom / middle."""
    lo, hi = min(series), max(series)
    if hi == lo:
        return "flat across"
    frac = (series[-1] - lo) / (hi - lo)
    if frac >= 0.8:
        return "near the top of"
    if frac <= 0.2:
        return "near the bottom of"
    return "in the middle of"


def ten_year_takeaway(
    *, ten_year: Optional[float], ten_year_history: list[float],
) -> str:
    """A read for the 10-year trend chart: level, week move (bps), range position."""
    full = [v for v in ten_year_history if v is not None]
    series = full[-_MONTH_SESSIONS:]
    if ten_year is None or len(series) < 2:
        return ""
    week_bps = None
    if len(series) >= 6:
        week_bps = (series[-1] - series[-6]) * 100.0
    pos = _range_position(series)
    parts = [f"The 10-year sits at {ten_year:.2f}%"]
    if week_bps is not None:
        if abs(week_bps) < 0.5:
            parts.append("little changed on the week")
        else:
            parts.append(f"{'up' if week_bps > 0 else 'down'} {abs(week_bps):.0f} bps on the week")
    parts.append(f"and {pos} its past-month range")
    return ", ".join(parts) + "."


def commodities_takeaway(histories: dict[str, list[float]]) -> str:
    """A read for the normalized commodities chart: each leg's month move."""
    moves: list[tuple[str, float]] = []
    for key, label, _ in _COMMODITY_LEGS:
        rebased = _rebased(histories.get(key, []))
        if rebased is None:
            continue
        moves.append((label, rebased[-1] - 100.0))
    if not moves:
        return ""
    leader = max(moves, key=lambda m: m[1])
    laggard = min(moves, key=lambda m: m[1])
    legs = ", ".join(f"{label} {chg:+.1f}%" for label, chg in moves)
    read = f"Rebased to 100 a month ago: {legs}."
    if leader[0] != laggard[0]:
        read += f" {leader[0]} leads and {laggard[0]} lags over the month."
    return read
