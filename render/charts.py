"""Static PNG charts, embedded inline (CID) so they show even when remote images
are blocked (spec §6; roadmap §7.11).

Three default-on charts: index daily %-change bar, yield curve + 10-year trend,
WTI 1-month trend. Others (VIX, movers, crypto, scorecard, watchlist sparklines)
are gated behind the config `charts` flags. Each builder returns a Chart (a CID +
PNG bytes); the caller (brief.py) decides which to build from config and attaches
the bytes to the email via render/send.py.

Pure: takes already-computed numbers and history lists, does no network and no
state access. matplotlib runs on the headless Agg backend.

Palette restyled to "The Tape" WHITE (HANDOFF_DESIGN charts decision): white
background, chart-blue #3a6ea5 trend line, mono tick labels, no chart-junk.
Green/red still carry direction only on the WTI fill. Each Chart carries a one-line
text summary so a blocked image still leaves a readable line (the template uses it
as the img alt text).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # headless: no display, deterministic PNG bytes
import matplotlib.pyplot as plt  # noqa: E402

# "The Tape" WHITE palette (HANDOFF_DESIGN). Blue is the single chart accent;
# green/red carry direction only (the WTI fill).
INK = "#1b1a17"
PAPER = "#FFFFFF"
HAIRLINE = "#E7E5E0"
BLUE = "#3a6ea5"
GREEN = "#0b7a3d"
RED = "#c0392b"
GREY = "#8a877f"

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
    """Apply the shared white palette to one axes (white face, hairline spines)."""
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


def _date_xaxis(ax, dates: list[str], n: int) -> str:
    """Label up to 4 x-ticks with real dates; return a 'May 20 - Jun 18' span label.

    `dates` is parallel to the n-point series (most-recent-last); entries may be ''
    for older pre-schema closes. Falls back to clean unlabeled ticks (and an empty
    span) when no usable dates are present, so the axis is never wrong.
    """
    labeled = [(i, _fmt_date(dates[i])) for i in range(n) if i < len(dates) and _fmt_date(dates[i])]
    if not labeled:
        ax.set_xticks([])
        return ""
    # Pick ~4 evenly spaced ticks from the points that have a real date.
    step = max(1, len(labeled) // 4)
    picks = labeled[::step]
    if labeled[-1] not in picks:
        picks.append(labeled[-1])
    ax.set_xticks([i for i, _ in picks])
    ax.set_xticklabels([lbl for _, lbl in picks], fontsize=7)
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


def _pad_ylim(ax, series: list[float], *, min_frac: float = 0.01) -> None:
    """Pad the y-limits so a small real range is not magnified into a sawtooth.

    A 14 bps move over a month is real but tiny; left to autoscale, matplotlib
    fills the panel and the line reads as random noise. We enforce a minimum
    visible span of `min_frac` of the series level (e.g. 1% of a 4.4% yield ~ 4
    bps floor) centered on the data, and add light headroom, so a quiet metric
    reads as a quiet, gently-sloped line.
    """
    lo, hi = min(series), max(series)
    mid = (lo + hi) / 2.0
    span = hi - lo
    floor = abs(mid) * min_frac
    half = max(span, floor) / 2.0 * 1.3  # 1.3 = light headroom above/below
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


def yield_curve_and_trend(
    *,
    ust2y: Optional[float],
    ust10y: Optional[float],
    ten_year_history: list[float],
    ten_year_dates: Optional[list[str]] = None,
    cid: str = "chart_rates",
) -> Optional[Chart]:
    """Yield curve (2s/10s) + the 10-year trend, fully labeled (spec §6 default-on).

    Two panels: left, the 2y vs 10y level with the 2s10s spread; right, the 10-year
    trend over the past month with a dated x-axis. Both carry unit labels and a
    "what it shows" subtitle. Returns None when neither panel can be drawn honestly.
    """
    have_curve = ust2y is not None and ust10y is not None
    full = [v for v in ten_year_history if v is not None]
    have_trend = len(full) >= 2
    if not have_curve and not have_trend:
        return None

    fig, (ax_curve, ax_trend) = plt.subplots(1, 2, figsize=(6.8, 2.9))
    fig.patch.set_facecolor(PAPER)
    for ax in (ax_curve, ax_trend):
        _style_axes(ax)

    if have_curve:
        spread = (ust10y - ust2y) * 100.0
        ax_curve.plot(["2-year", "10-year"], [ust2y, ust10y], marker="o", color=BLUE, linewidth=1.8)
        _titled(ax_curve, "Treasury yield curve, today", f"2s10s spread {spread:+.0f} bps")
        ax_curve.set_ylabel("Yield (%)", color=GREY, fontsize=8, **_CHART_FONT)
        for label, val in (("2-year", ust2y), ("10-year", ust10y)):
            ax_curve.annotate(f"{val:.2f}%", (label, val), textcoords="offset points",
                              xytext=(0, 7), ha="center", color=INK, fontsize=9, fontweight="bold")
        _pad_ylim(ax_curve, [ust2y, ust10y], min_frac=0.05)
    else:
        ax_curve.axis("off")

    if have_trend:
        series = full[-_MONTH_SESSIONS:]
        n = len(series)
        win_dates = (ten_year_dates or [])[-len(full):][-n:]
        ax_trend.plot(range(n), series, color=BLUE, linewidth=1.8)
        span = _date_xaxis(ax_trend, win_dates, n)
        _titled(ax_trend, "10-year yield, past month",
                "Daily close" + (f"  ·  {span}" if span else ""))
        ax_trend.set_ylabel("Yield (%)", color=GREY, fontsize=8, **_CHART_FONT)
        ax_trend.annotate(f"{series[-1]:.2f}%", (n - 1, series[-1]), textcoords="offset points",
                          xytext=(-2, 6), ha="right", color=INK, fontsize=9, fontweight="bold")
        _pad_ylim(ax_trend, series)
    else:
        ax_trend.axis("off")

    fig.tight_layout()
    bits = []
    if have_curve:
        bits.append(f"2Y {ust2y:.2f}%, 10Y {ust10y:.2f}% (2s10s {(ust10y - ust2y) * 100:+.0f} bps)")
    if have_trend:
        bits.append(f"10-year {full[-1]:.2f}%, past month")
    return Chart(cid=cid, png=_to_png(fig), title="Rates", summary="Treasury yields: " + "; ".join(bits))


def wti_trend(
    history: list[float], *, dates: Optional[list[str]] = None, cid: str = "chart_oil",
) -> Optional[Chart]:
    """WTI crude trailing one-month trend, fully labeled (spec §6 default-on).

    Clamps to the last ~21 sessions so the chart shows a month, not the entire
    rolling backfill. Renders a title + "what it shows" subtitle, a dated x-axis,
    a unit-labeled y-axis, and annotated start/end values. Returns None on thin data.
    """
    full = [v for v in history if v is not None]
    series = full[-_MONTH_SESSIONS:]
    if len(series) < 2:
        return None
    n = len(series)
    win_dates = (dates or [])[-len(full):][-n:]  # align dates to the clamped window

    fig, ax = _new_axes(5.0, 2.8)
    rising = series[-1] >= series[0]
    ax.plot(range(n), series, color=BLUE, linewidth=1.8)
    ax.fill_between(range(n), series, min(series), color=(GREEN if rising else RED), alpha=0.08)
    span = _date_xaxis(ax, win_dates, n)
    _titled(ax, "WTI crude oil, past month",
            "Front-month futures, daily close" + (f"  ·  {span}" if span else ""))
    ax.set_ylabel("USD / barrel", color=GREY, fontsize=8, **_CHART_FONT)
    # Annotate both endpoints so the move is legible at a glance.
    ax.annotate(f"${series[0]:,.0f}", (0, series[0]), textcoords="offset points",
                xytext=(2, 6), ha="left", color=GREY, fontsize=8)
    ax.annotate(f"${series[-1]:,.2f}", (n - 1, series[-1]), textcoords="offset points",
                xytext=(-2, 6), ha="right", color=INK, fontsize=9, fontweight="bold")
    fig.tight_layout()
    pct = (series[-1] - series[0]) / series[0] * 100.0 if series[0] else 0.0
    summary = (f"WTI crude, past month: ${series[-1]:,.2f}, "
               f"{'up' if rising else 'down'} {abs(pct):.1f}% from ${series[0]:,.2f}")
    return Chart(cid=cid, png=_to_png(fig), title="WTI crude", summary=summary)
