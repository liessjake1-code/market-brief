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
    cid: str = "chart_rates",
) -> Optional[Chart]:
    """Yield curve snapshot (2s/10s) plus the 10-year trend (spec §6 default-on).

    Two panels: left, the 2y vs 10y level; right, the 10-year recent trend line.
    Returns None when there is not enough to draw either panel honestly.
    """
    have_curve = ust2y is not None and ust10y is not None
    have_trend = len([v for v in ten_year_history if v is not None]) >= 2
    if not have_curve and not have_trend:
        return None

    fig, (ax_curve, ax_trend) = plt.subplots(1, 2, figsize=(6.4, 2.6))
    fig.patch.set_facecolor(PAPER)
    for ax in (ax_curve, ax_trend):
        _style_axes(ax)

    if have_curve:
        ax_curve.plot(["2Y", "10Y"], [ust2y, ust10y], marker="o", color=BLUE, linewidth=1.6)
        ax_curve.set_title("Yield curve", color=INK, fontsize=10, **_CHART_FONT)
        for label, val in (("2Y", ust2y), ("10Y", ust10y)):
            ax_curve.annotate(f"{val:.2f}%", (label, val), textcoords="offset points",
                              xytext=(0, 6), ha="center", color=GREY, fontsize=8)
    else:
        ax_curve.axis("off")

    if have_trend:
        series = [v for v in ten_year_history if v is not None]
        ax_trend.plot(range(len(series)), series, color=BLUE, linewidth=1.8)
        ax_trend.set_title("10-year trend", color=INK, fontsize=10, **_CHART_FONT)
        ax_trend.set_xticks([])
    else:
        ax_trend.axis("off")

    fig.tight_layout()
    bits = []
    if have_curve:
        bits.append(f"2Y {ust2y:.2f}%, 10Y {ust10y:.2f}% (2s10s {(ust10y - ust2y) * 100:+.0f} bps)")
    if have_trend:
        bits.append("10-year trend shown")
    return Chart(cid=cid, png=_to_png(fig), title="Rates", summary="Yield curve: " + "; ".join(bits))


def wti_trend(history: list[float], *, cid: str = "chart_oil") -> Optional[Chart]:
    """WTI crude 1-month trend (spec §6 default-on). Returns None on thin data."""
    series = [v for v in history if v is not None]
    if len(series) < 2:
        return None
    fig, ax = _new_axes(4.8, 2.6)
    rising = series[-1] >= series[0]
    # Trend line stays the blue accent; the fill carries direction (green/red).
    ax.plot(range(len(series)), series, color=BLUE, linewidth=1.8)
    ax.fill_between(range(len(series)), series, min(series),
                    color=(GREEN if rising else RED), alpha=0.08)
    ax.set_title("WTI crude, recent trend", color=INK, fontsize=10, **_CHART_FONT)
    ax.set_xticks([])
    ax.annotate(f"${series[-1]:,.2f}", (len(series) - 1, series[-1]),
                textcoords="offset points", xytext=(-4, 6), ha="right",
                color=INK, fontsize=8)
    pct = (series[-1] - series[0]) / series[0] * 100.0 if series[0] else 0.0
    summary = f"WTI crude recent trend: ${series[-1]:,.2f}, {'up' if rising else 'down'} {abs(pct):.1f}% over the window"
    return Chart(cid=cid, png=_to_png(fig), title="WTI crude", summary=summary)
