"""brief.py — main entry: gather, build, send (spec §8.5; roadmap §5).

Pipeline as of Phase 5 (templated lines; the model arrives in Phase 6, the full
editorial template in Phase 7):

    load config + state -> pull fields -> health check
      -> hard floor? send "data unavailable" notice + exit non-zero
      -> else build a templated brief -> send (unless --no-send)
      -> on a real send: stamp state + commit back (Actions only)

LOAD-BEARING invariant (Phase 1): --no-send implies NO state write. All state
writes funnel through _commit_state(), a hard no-op under --no-send, so a test or
partial build can never poison the next day's diff or the idempotency guard.
The brief never blocks on the model or news (spec §5.6); degraded runs still ship.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import os

from engine import diff as diff_mod
from engine import schedule as sch
from engine import state as state_mod
from engine import top_story as top_story_mod
from engine.config import load_config
from render import charts as charts_mod
from render import html as html_render
from render import templated
from render import viewmodel as vm
from render.send import send as smtp_send
from sources import calendar as calendar_mod
from sources import prices
from sources.quality import Field, Source, assess

EXIT_OK = 0
EXIT_HARD_FLOOR = 2

# Test/CI seam: when MARKET_BRIEF_OFFLINE=1, skip all network pulls and synthesize
# clean placeholder fields. This lets the smoke test and the --no-send invariant
# test run deterministically without yfinance or a network, while production runs
# (env unset) always do the real pull.
_OFFLINE_ENV = "MARKET_BRIEF_OFFLINE"


def build_brief(*, send: bool, today: date | None = None) -> int:
    today = today or date.today()
    print("Daily Market Brief")
    print(f"  mode: {'FULL RUN (send + state write)' if send else 'NO-SEND (build only, no state write)'}")

    cfg = load_config()
    resilience = cfg["resilience"]

    # --- gather (Phase 5) ------------------------------------------------ #
    fields = _gather_fields()
    report = assess(
        fields,
        degraded_stale_threshold=int(resilience["degraded_stale_threshold"]),
        hard_floor_missing_threshold=int(resilience["hard_floor_missing_threshold"]),
    )
    print(f"  health: missing_core={report.missing_core} stale_core={report.stale_core} "
          f"degraded={report.degraded}")

    # --- hard floor: never ship a broken brief (spec §7.5) --------------- #
    if report.hard_floor_tripped:
        print("  hard floor TRIPPED: too many core fields missing.")
        if send:
            smtp_send(
                subject=f"Market brief unavailable — {today.isoformat()}",
                html=templated.DATA_UNAVAILABLE_HTML,
                text_fallback="Market brief unavailable: too many core fields missing.",
            )
        # Exit non-zero so the failed run is visible in Actions (spec §7.5).
        return EXIT_HARD_FLOOR

    # --- explanation engine (Phase 6); degrades to templated lines ------- #
    narrative_results, narrative_degraded = _run_narrative(cfg, report, today)
    if narrative_degraded:
        report.degraded = True

    # --- build the editorial brief (Phase 7: view-model -> Jinja) -------- #
    # Charts and render are wrapped so a matplotlib/Jinja failure degrades to a
    # chart-free (or templated) brief rather than killing the send (spec §5.6).
    prose_by_section = _brief_lines(report, narrative_results)
    html, inline_images = _build_html(cfg, today, report, prose_by_section)

    if send:
        decision = sch.decide_send(
            send_time=cfg["send_time"],
            send_window_end=cfg["send_window_end"],
            last_sent_date=_last_sent_date(),
        )
        print(f"  schedule: {decision.reason}")
        if decision.should_send:
            smtp_send(subject=_subject(today, report), html=html, inline_images=inline_images)
            print(f"  send: sent ({len(inline_images)} inline chart(s))")
        else:
            print("  send: skipped by guard")
            send = False  # do not write state if we did not actually send
    else:
        print("  send: skipped (--no-send)")
        preview_path = _write_preview(html)
        print(f"  preview: wrote {preview_path}")

    _commit_state(send=send, today=today, fields=report.fields)
    return EXIT_OK


def _write_preview(html: str) -> str:
    """Write the rendered brief to a gitignored preview file for inspection.

    Uses a name matched by .gitignore (*.preview.html) so a no-send build is never
    committed. Build-only side effect; never touches state (no-send invariant).
    """
    repo_root = os.path.dirname(os.path.abspath(__file__))
    name = "brief.preview.html"
    with open(os.path.join(repo_root, name), "w", encoding="utf-8") as fh:
        fh.write(html)
    return name


def _gather_fields() -> dict[str, Field]:
    """Pull real fields, or synthesize clean placeholders when offline (test/CI)."""
    if os.environ.get(_OFFLINE_ENV) == "1":
        from engine.metrics import METRIC_KEYS
        return {k: Field(k, 100.0, Source.YFINANCE) for k in METRIC_KEYS}
    return prices.pull_fields()


def _templated_brief(report) -> dict[str, str]:
    """One flat line per metric from numbers + direction (no model, no causes)."""
    out: dict[str, str] = {}
    for key, field in report.fields.items():
        out[key] = templated.templated_line(field, change=None)
    return out


# Map each narrative section to the metric keys whose numbers ground it.
_SECTION_METRICS: dict[str, tuple[str, ...]] = {
    "us_equities": ("sp500", "nasdaq", "dow", "russell"),
    "rates_and_dollar": ("ust10y", "ust2y", "dxy"),
    "commodities": ("wti", "gold"),
    "crypto": ("btc", "eth"),
    "volatility_breadth": ("vix",),
}


def _run_narrative(cfg, report, today):
    """Run the explanation engine when enabled; else templated lines (spec §5.6).

    Skipped offline and when the model is disabled or unkeyed, so the brief always
    ships. Returns (results_by_section, degraded).
    """
    narrative_cfg = cfg.get("narrative", {})
    offline = os.environ.get(_OFFLINE_ENV) == "1"
    if offline or not narrative_cfg.get("enabled") or not os.environ.get("ANTHROPIC_API_KEY"):
        print("  narrative: templated (model disabled/offline/unkeyed)")
        return {}, False

    from engine import narrative as narr
    from sources import news as news_mod

    section_numbers = _section_numbers(report)
    articles = news_mod.fetch_articles()
    bundles = narr.build_bundles(section_numbers, articles,
                                 watchlist_tickers=cfg.get("watchlist") or [])
    results, degraded, raw = narr.generate(
        bundles,
        model=narrative_cfg.get("model", "claude-sonnet-4-6"),
        tolerance_pct=float(narrative_cfg.get("number_tolerance_pct", 0.05)),
        templated_fallback=lambda sid: _section_template_line(report, sid),
    )
    runs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
    narr.dump_run(results, raw, runs_dir=runs_dir, date_str=today.isoformat())
    print(f"  narrative: model run, degraded={degraded}")
    return results, degraded


def _section_numbers(report) -> dict[str, dict[str, float]]:
    """Per-section usable numbers for the model (only non-stale, present fields)."""
    out: dict[str, dict[str, float]] = {}
    for section, keys in _SECTION_METRICS.items():
        nums = {k: report.fields[k].value for k in keys
                if k in report.fields and report.fields[k].is_usable}
        if nums:
            out[section] = nums
    return out


def _section_template_line(report, section_id: str) -> str:
    keys = _SECTION_METRICS.get(section_id, ())
    for k in keys:
        if k in report.fields:
            return templated.templated_line(report.fields[k], change=None)
    return f"{section_id}: no clear catalyst."


def _brief_lines(report, narrative_results) -> dict[str, str]:
    """Prefer model prose per section; fall back to per-metric templated lines."""
    if narrative_results:
        return {sid: res.prose for sid, res in narrative_results.items()}
    return _templated_brief(report)


def _build_html(cfg, today: date, report, prose_by_section: dict[str, str]):
    """Build (html, inline_images), degrading rather than crashing (spec §5.6).

    Charts and the Jinja render are the only Phase 7 stages that can raise on the
    runner (matplotlib backend, a malformed view field). If charts fail we ship a
    chart-free degraded brief; if the whole render fails we fall back to the flat
    templated HTML so an email always goes out.
    """
    try:
        charts = _build_charts(cfg, report)
    except Exception as exc:  # never let a chart failure sink the brief
        print(f"  charts: FAILED, shipping chart-free ({exc!r})")
        charts, report.degraded = [], True

    chart_cids = tuple(c.cid for c in charts)
    inline_images = [(c.cid, c.png) for c in charts]
    try:
        view = _build_view(cfg, today, report, prose_by_section, chart_cids=chart_cids)
        return html_render.render_brief(view), inline_images
    except Exception as exc:  # last-resort: a flat brief beats no brief
        print(f"  render: FAILED, falling back to flat HTML ({exc!r})")
        report.degraded = True
        return _fallback_html(today, report, prose_by_section), []


def _fallback_html(today: date, report, prose_by_section: dict[str, str]) -> str:
    """Minimal flat HTML if the editorial render raises. Never blocks the send."""
    rows = "".join(f"<li>{line}</li>" for line in prose_by_section.values())
    return (
        "<html><body style='font-family:Georgia,serif;color:#13202E'>"
        f"<h2>Morning Market Brief</h2><p>{today.isoformat()}</p>"
        "<p style='background:#FBE9E7;border:1px solid #BC3B2E;padding:8px'>"
        "Degraded run: the editorial template could not render; showing flat lines.</p>"
        f"<ul style=\"font-family:Consolas,'SFMono-Regular',monospace\">{rows}</ul>"
        "</body></html>"
    )


def _build_view(
    cfg, today: date, report, prose_by_section: dict[str, str], *, chart_cids: tuple[str, ...] = (),
) -> vm.BriefView:
    """Assemble the validated view-model the template renders (Phase 7).

    Pulls the diff line and Top Story order from cached state when present (both
    degrade to quiet/fallback when state is missing, e.g. offline/first run), the
    secondary calendar best-effort, and labels the live zone by actual pull time.
    Nothing here invents a number or a cause (spec §1, §2).
    """
    live_label = sch.premarket_label()
    diff_line, order, top_story_id = _diff_and_order(report, today)

    # Section "why" for the At a Glance table reuses the (short) section prose.
    section_why = {sid: _first_sentence(text) for sid, text in prose_by_section.items()}

    cal = _load_calendar(cfg, today)
    forward_events = tuple({"time_label": e.time_label, "title": e.title} for e in cal.events)
    earnings = tuple({"ticker": e.ticker, "when": e.when} for e in cal.earnings if e.when == "bmo") \
        or tuple({"ticker": e.ticker, "when": e.when} for e in cal.earnings)
    # A failed optional calendar is a degraded run; flag it (read-once, no later mutation).
    degraded = report.degraded or cal.degraded

    glance_rows = vm.build_glance_rows(
        report.fields, section_why,
        live_label=live_label,
        live_why="Pre-market futures and overnight moves, labeled and provisional.",
        events_why=_events_summary(cal),
        earnings_why=_earnings_summary(cal),
        washington_why=section_why.get("washington", "No market-moving policy news flagged."),
        bottom_line=_bottom_line(degraded, diff_line),
    )

    favicon_tickers = _favicon_tickers(cfg)
    sections = vm.build_sections(
        order, prose_by_section, top_story_id=top_story_id, favicon_tickers=favicon_tickers,
    )

    return vm.BriefView(
        date_label=_long_date(today),
        send_label=f"Sent {live_label}",
        degraded=degraded,
        diff_line=diff_line,
        glance_rows=glance_rows,
        sections=sections,
        live_label=live_label,
        live_figures=(),  # populated once a live pre-market pull is wired (best-effort)
        forward_events=forward_events,
        earnings=earnings,
        chart_cids=chart_cids,
    )


def _build_charts(cfg, report) -> list[charts_mod.Chart]:
    """Build the enabled default-on charts from settled fields + history (Phase 7).

    Each builder returns None on thin data and is simply skipped; a chart is never
    forced. Offline/no-state runs still render the brief without charts. History is
    loaded once and shared across all three builders.
    """
    flags = cfg.get("charts", {}) or {}
    history = _state_history()
    built: list[charts_mod.Chart] = []

    if flags.get("index_bar"):
        chart = charts_mod.index_change_bar(_index_changes(history))
        if chart:
            built.append(chart)
    if flags.get("yield_curve"):
        chart = charts_mod.yield_curve_and_trend(
            ust2y=_usable_value(report, "ust2y"),
            ust10y=_usable_value(report, "ust10y"),
            ten_year_history=history.get("ust10y", []),
        )
        if chart:
            built.append(chart)
    if flags.get("oil_trend"):
        chart = charts_mod.wti_trend(history.get("wti", []))
        if chart:
            built.append(chart)
    return built


def _long_date(today: date) -> str:
    """Long date label without the platform-specific %-d directive (portable)."""
    return f"{today:%A, %B} {today.day}, {today.year}"


def _diff_and_order(report, today: date):
    """Diff line + Top Story section order, from cached state. Degrades gracefully."""
    try:
        st = state_mod.load_state(today=today)
    except (FileNotFoundError, ValueError):
        st = None
    if st is None or st.missing:
        return diff_mod.QUIET_TAPE_LINE, list(top_story_mod.FALLBACK_ORDER), "us_equities"
    stale = report.stale_keys
    diff_res = diff_mod.compute_diff(st, stale_keys=stale)
    decision = top_story_mod.decide(st, day=today, stale_keys=stale)
    return diff_res.line, decision.order, decision.section


def _load_calendar(cfg, today: date) -> calendar_mod.CalendarData:
    if os.environ.get(_OFFLINE_ENV) == "1":
        return calendar_mod.CalendarData()
    return calendar_mod.fetch_calendar(today)


def _state_history() -> dict[str, list[float]]:
    try:
        st = state_mod.load_state()
    except (FileNotFoundError, ValueError):
        return {}
    if st.missing:
        return {}
    from engine.metrics import METRIC_KEYS
    return {k: st.history(k) for k in METRIC_KEYS}


def _index_changes(history: dict[str, list[float]]) -> dict[str, float]:
    """Per-index daily %-change from settled history, for the index bar chart."""
    labels = {"sp500": "S&P 500", "nasdaq": "Nasdaq", "dow": "Dow", "russell": "Russell"}
    out: dict[str, float] = {}
    for key, label in labels.items():
        hist = history.get(key, [])
        if len(hist) >= 2 and hist[-2]:
            out[label] = (hist[-1] - hist[-2]) / hist[-2] * 100.0
    return out


def _usable_value(report, key: str):
    f = report.fields.get(key)
    return f.value if f and f.is_usable else None


def _favicon_tickers(cfg) -> dict[str, list[dict]]:
    """Watchlist/movers tickers with their config domain map, for favicon rows."""
    domains = cfg.get("ticker_domains", {}) or {}
    watchlist = cfg.get("watchlist", []) or []
    movers = cfg.get("movers_universe", []) or []
    return {
        "watchlist": [{"ticker": t, "domain": domains.get(t)} for t in watchlist],
        "movers": [{"ticker": t, "domain": domains.get(t)} for t in movers],
    }


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    for sep in (". ", "; "):
        if sep in text:
            return text.split(sep, 1)[0].rstrip(".;") + "."
    return text


def _events_summary(cal: calendar_mod.CalendarData) -> str:
    if not cal.events:
        return "No major scheduled releases."
    return ", ".join(e.title for e in cal.events[:3])


def _earnings_summary(cal: calendar_mod.CalendarData) -> str:
    pre = [e.ticker for e in cal.earnings if e.when == "bmo"]
    if pre:
        return ", ".join(pre[:5])
    if cal.earnings:
        return ", ".join(e.ticker for e in cal.earnings[:5])
    return "None flagged before the open."


def _bottom_line(degraded: bool, diff_line: str) -> str:
    if degraded:
        return "Degraded run; read the figures with that caveat."
    if diff_line == diff_mod.QUIET_TAPE_LINE:
        return "Quiet tape; little to act on."
    return _first_sentence(diff_line)


def _subject(today: date, report) -> str:
    tag = " [degraded]" if report.degraded else ""
    return f"Morning Market Brief — {today:%b %-d}{tag}"


def _last_sent_date() -> str | None:
    try:
        return state_mod.load_state().data.get("last_sent_date")
    except (FileNotFoundError, ValueError):
        return None


def _commit_state(*, send: bool, today: date | None = None, fields=None) -> None:
    """Single choke point for ALL state writes (spec §8.5 invariant).

    Under --no-send (or when the guard skipped the send) this is an unconditional
    no-op: no last_run.json, no last_sent_date. On a real send it stamps and
    commits state back (Actions-only PAT commit, spec §8.3).
    """
    if not send:
        print("  state: no write (no-send / not sent) [invariant]")
        return
    st = state_mod.load_state()
    if st.missing and os.environ.get(_OFFLINE_ENV) != "1":
        st = state_mod.backfill(prices.fetch_history)
    if fields:
        for key, field in fields.items():
            if field.is_usable and key in st.data["metrics"]:
                metric = st.data["metrics"][key]
                hist = list(metric.get("history", []))
                hist.append(field.value)
                metric["history"] = hist
                metric["prev_close"] = metric.get("close")
                metric["close"] = field.value
    st.data["last_sent_date"] = (today or date.today()).isoformat()
    st.data["sent_today"] = True
    state_mod.save_state(st)
    state_mod.commit_state_back()
    print("  state: written + commit-back attempted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="brief.py",
        description="Daily Market Brief: gather, build, and send the weekday brief.",
    )
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Build only: do NOT send and do NOT write state.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return build_brief(send=not args.no_send)


if __name__ == "__main__":
    sys.exit(main())
