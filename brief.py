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
from engine import movers as movers_mod
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
from sources import stocks as stocks_mod
from sources.quality import Field, Source, assess

EXIT_OK = 0
EXIT_HARD_FLOOR = 2

# Test/CI seam: when MARKET_BRIEF_OFFLINE=1, skip all network pulls and synthesize
# clean placeholder fields. This lets the smoke test and the --no-send invariant
# test run deterministically without yfinance or a network, while production runs
# (env unset) always do the real pull.
_OFFLINE_ENV = "MARKET_BRIEF_OFFLINE"

# Honest note shown in "What to Watch" when the OPTIONAL events calendar could not
# be retrieved. This is a per-section caveat, NOT the whole-brief degraded banner
# (spec §7.5: the banner is for stale core data or a failed model only).
_CALENDAR_DEGRADED_NOTE = (
    "Scheduled-events feed unavailable this morning; check an economic calendar directly."
)


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

    # --- per-stock data for Watchlist/Movers (best-effort, never core) --- #
    # A stock-fetch failure is a non-event: it never trips the banner or hard floor
    # (those stay core-metric/model only). select_movers applies the spec §7
    # best-effort rule (watchlist-only by default, upgrade on a reliable screen).
    stock_quotes = _gather_stocks(cfg)
    movers_sel = movers_mod.select_movers(
        stock_quotes,
        watchlist=cfg.get("watchlist") or [],
        universe=cfg.get("movers_universe") or [],
        min_volume=float(cfg.get("movers_min_volume", 0) or 0),
    )

    # --- explanation engine (Phase 6); degrades to templated lines ------- #
    narrative_results, narrative_degraded = _run_narrative(
        cfg, report, today, stock_quotes=stock_quotes, movers_sel=movers_sel,
    )
    if narrative_degraded:
        report.degraded = True

    # --- build the editorial brief (Phase 7: view-model -> Jinja) -------- #
    # Charts and render are wrapped so a matplotlib/Jinja failure degrades to a
    # chart-free (or templated) brief rather than killing the send (spec §5.6).
    prose_by_section = _brief_lines(report, narrative_results)
    html, inline_images = _build_html(
        cfg, today, report, prose_by_section, narrative_results,
        stock_quotes=stock_quotes, movers_sel=movers_sel,
    )

    if send:
        allow_repeat = bool(cfg.get("monitoring", {}).get("allow_repeat_send", False))
        if allow_repeat:
            print("  schedule: allow_repeat_send ON (idempotency guard bypassed — TEMPORARY)")
        decision = sch.decide_send(
            send_time=cfg["send_time"],
            send_window_end=cfg["send_window_end"],
            last_sent_date=_last_sent_date(),
            allow_repeat_send=allow_repeat,
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

    _commit_state(send=send, today=today, fields=report.fields, stock_quotes=stock_quotes)
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


def _stock_universe(cfg) -> list[str]:
    """The de-duped union of watchlist + movers_universe, in a stable order."""
    seen: dict[str, None] = {}
    for ticker in (cfg.get("watchlist") or []) + (cfg.get("movers_universe") or []):
        seen.setdefault(ticker, None)
    return list(seen.keys())


def _gather_stocks(cfg) -> dict[str, stocks_mod.StockQuote]:
    """Best-effort per-stock pull for Watchlist/Movers; {} when offline or empty.

    Never raises and never feeds the degraded banner (stocks are not core data).
    """
    if os.environ.get(_OFFLINE_ENV) == "1":
        return {}
    tickers = _stock_universe(cfg)
    if not tickers:
        return {}
    quotes = stocks_mod.fetch_stocks(tickers, days=state_mod.STOCK_HISTORY_KEEP)
    print(f"  stocks: pulled {len(quotes)}/{len(tickers)} tickers")
    return quotes


# Map each narrative section to the metric keys whose numbers ground it.
_SECTION_METRICS: dict[str, tuple[str, ...]] = {
    "us_equities": ("sp500", "nasdaq", "dow", "russell"),
    "rates_and_dollar": ("ust10y", "ust2y", "dxy"),
    "commodities": ("wti", "gold"),
    "crypto": ("btc", "eth"),
    "volatility_breadth": ("vix",),
}


def _company_names(cfg) -> dict[str, str]:
    """Best-effort ticker -> company name from the config domain map for matching.

    e.g. NVDA -> "nvidia" from nvidia.com. Used only as an extra news-match keyword
    (the ticker symbol itself always matches), so a missing/odd name just narrows
    matching to the symbol. Never load-bearing.
    """
    domains = cfg.get("ticker_domains", {}) or {}
    out: dict[str, str] = {}
    for ticker, domain in domains.items():
        if isinstance(domain, str) and "." in domain:
            out[ticker] = domain.split(".")[0]
    return out


def _stock_tickers_in_play(cfg, movers_sel) -> list[str]:
    """The tickers that need a per-stock 'why': watchlist + the selected movers."""
    seen: dict[str, None] = {}
    for ticker in (cfg.get("watchlist") or []):
        seen.setdefault(ticker, None)
    for m in movers_sel.movers:
        seen.setdefault(m.ticker, None)
    return list(seen.keys())


def _run_narrative(cfg, report, today, *, stock_quotes=None, movers_sel=None):
    """Run the explanation engine when enabled; else templated lines (spec §5.6).

    Skipped offline and when the model is disabled or unkeyed, so the brief always
    ships. Folds per-stock pseudo-sections (keyed 'stock:<TICKER>') for the watchlist
    + selected movers into the SAME single call. Returns (results_by_section, degraded).
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
    # Per-stock "why" bundles for the tickers actually shown (watchlist + movers).
    if movers_sel is not None:
        stock_tickers = _stock_tickers_in_play(cfg, movers_sel)
        bundles += narr.build_stock_bundles(
            stock_tickers, articles, company_names=_company_names(cfg),
        )
    results, degraded, raw = narr.generate(
        bundles,
        model=narrative_cfg.get("model", "claude-sonnet-4-6"),
        tolerance_pct=float(narrative_cfg.get("number_tolerance_pct", 0.05)),
        templated_fallback=lambda sid: _stock_or_section_fallback(report, sid),
    )
    runs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
    narr.dump_run(results, raw, runs_dir=runs_dir, date_str=today.isoformat())
    print(f"  narrative: model run, degraded={degraded}")
    return results, degraded


def _stock_or_section_fallback(report, section_id: str) -> str:
    """Templated fallback: a quiet line for a stock pseudo-section, else the section line."""
    if section_id.startswith(narr_stock_prefix()):
        return "no clear catalyst"
    return _section_template_line(report, section_id)


def narr_stock_prefix() -> str:
    from engine import narrative as narr
    return narr.STOCK_SECTION_PREFIX


def _section_numbers(report) -> dict[str, dict[str, float]]:
    """Per-section usable numbers for the model, with derived week/month figures.

    The model may only state numbers in this set (spec §1, §6.2), so we compute
    everything it is allowed to say: the current value plus the trailing week and
    month change per metric, from rolling history. The number validator then
    accepts "up about 1.8% on the week" because 1.8 is a supplied input. Derived
    figures are added under suffixed keys so they are present but unobtrusive.
    """
    from engine import context as ctx_mod

    history = _state_history()
    out: dict[str, dict[str, float]] = {}
    for section, keys in _SECTION_METRICS.items():
        nums: dict[str, float] = {}
        for k in keys:
            field = report.fields.get(k)
            if not (field and field.is_usable):
                continue
            nums[k] = field.value
            ctx = ctx_mod.time_context(history.get(k, []), k)
            if ctx.week_change is not None:
                nums[f"{k}_week_change"] = round(ctx.week_change, 2)
            if ctx.month_change is not None:
                nums[f"{k}_month_change"] = round(ctx.month_change, 2)
        if nums:
            out[section] = nums
    return out


def _section_template_line(report, section_id: str) -> str:
    """Rich, cause-free computed line for a section (redesign "no empty sections").

    Uses the section's representative metric + its rolling history to build the
    four-ingredient read minus the causal "why" (spec §5.6). Falls back to the
    plain per-metric line if the section has no grounding metric.
    """
    keys = _SECTION_METRICS.get(section_id, ())
    history = _state_history()
    for k in keys:
        if k in report.fields:
            return templated.computed_section_line(
                report.fields[k], history.get(k, []), section_id=section_id,
            )
    return f"{section_id}: no clear catalyst flagged."


def _brief_lines(report, narrative_results) -> dict[str, str]:
    """Build each rendered section line: accurate Python numbers + model's cause.

    Accuracy is structural (spec §1): the numbers sentence is always computed in
    Python from the data, so it cannot be wrong. The model contributes only the
    number-free causal clause. A section whose model output was rejected (templated)
    carries the computed line alone ("no clear catalyst") — honest, not bare. When
    the model did not run at all, every section is the computed line.
    """
    if not narrative_results:
        return {sid: _section_template_line(report, sid) for sid in _SECTION_METRICS}

    history = _state_history()
    out: dict[str, str] = {}
    for sid, res in narrative_results.items():
        if sid.startswith(narr_stock_prefix()):
            continue  # per-stock pseudo-sections render via stock_notes, not body prose
        field = _representative_field(report, sid)
        if res.templated or field is None:
            # Model rejected (templated_fallback already set res.prose to the
            # computed line), or no grounding metric: the computed line stands alone.
            out[sid] = res.prose
        else:
            # Accurate numbers + the validated, number-free cause.
            out[sid] = templated.section_with_cause(field, history.get(field.metric, []), res.prose)
    return out


def _representative_field(report, section_id: str):
    """The first usable grounding field for a section, or None."""
    for k in _SECTION_METRICS.get(section_id, ()):
        f = report.fields.get(k)
        if f is not None:
            return f
    return None


def _build_html(cfg, today: date, report, prose_by_section: dict[str, str], narrative_results,
                *, stock_quotes=None, movers_sel=None):
    """Build (html, inline_images), degrading rather than crashing (spec §5.6).

    Charts and the Jinja render are the only Phase 7 stages that can raise on the
    runner (matplotlib backend, a malformed view field). If charts fail we ship a
    chart-free degraded brief; if the whole render fails we fall back to the flat
    templated HTML so an email always goes out. PNG charts attach inline to their
    section (rates -> yield curve, commodities -> WTI); the index bar and watchlist
    sparklines are inline HTML drawn in the template, not images.
    """
    try:
        charts_by_section = _build_charts(cfg, report)
    except Exception as exc:  # never let a chart failure sink the brief
        print(f"  charts: FAILED, shipping chart-free ({exc!r})")
        charts_by_section, report.degraded = {}, True

    inline_images = [(c.cid, c.png) for c in charts_by_section.values()]
    takeaways = _chart_takeaways(report)
    section_charts = {
        sid: {"cid": c.cid, "caption": cap, "caption_url": url,
              "takeaway": takeaways.get(sid, c.summary)}
        for sid, (c, cap, url) in _CHART_CAPTIONS_FROM(charts_by_section).items()
    }
    try:
        view = _build_view(
            cfg, today, report, prose_by_section, narrative_results,
            section_charts=section_charts,
            stock_quotes=stock_quotes, movers_sel=movers_sel,
        )
        return html_render.render_brief(view), inline_images
    except Exception as exc:  # last-resort: a flat brief beats no brief
        print(f"  render: FAILED, falling back to flat HTML ({exc!r})")
        report.degraded = True
        return _fallback_html(today, report, prose_by_section), []


# Caption text + live-chart link per PNG-charted section (spec §7 chart attribution).
# The URL is the live, interactive, zoomable chart page (FRED / Yahoo); the email
# image links out to it since email cannot host an interactive chart.
_CHART_META: dict[str, tuple[str, str]] = {
    "rates_and_dollar": ("Source: FRED (DGS10)", "https://fred.stlouisfed.org/series/DGS10"),
    "commodities": ("Source: Yahoo Finance (CL=F, GC=F, HG=F)", "https://finance.yahoo.com/chart/CL=F"),
}


def _chart_takeaways(report) -> dict[str, str]:
    """Python-computed 'what this tells you' line per charted section (accuracy-safe).

    Every figure in these reads is computed straight from the data, so the chart
    explanation can never carry a wrong number (spec §1, redesign item 5).
    """
    history = _state_history()
    return {
        "rates_and_dollar": charts_mod.ten_year_takeaway(
            ten_year=_usable_value(report, "ust10y"),
            ten_year_history=history.get("ust10y", []),
        ),
        "commodities": charts_mod.commodities_takeaway(
            {k: history.get(k, []) for k in ("wti", "gold", "copper")},
        ),
    }


def _CHART_CAPTIONS_FROM(charts_by_section):
    """Attach the caption text + url to each section's chart (read-only join)."""
    out = {}
    for sid, chart in charts_by_section.items():
        caption, url = _CHART_META.get(sid, (chart.summary, ""))
        out[sid] = (chart, caption, url)
    return out


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
    cfg, today: date, report, prose_by_section: dict[str, str], narrative_results,
    *, section_charts: dict[str, dict] | None = None,
    stock_quotes=None, movers_sel=None,
) -> vm.BriefView:
    """Assemble the validated view-model the template renders (Phase 7 + redesign).

    Pulls the diff line and Top Story order from cached state when present (both
    degrade to quiet/fallback when state is missing, e.g. offline/first run), the
    secondary calendar best-effort, and labels the live zone by actual pull time.
    Threads per-section citations from the validated narrative, the inline HTML
    charts (index bars, watchlist sparklines) drawn from history, and the four
    text rows of At a Glance. Nothing here invents a number or a cause (spec §1, §2).
    """
    section_charts = section_charts or {}
    live_label = sch.premarket_label()
    diff_line, order, top_story_id = _diff_and_order(report, today)
    history = _state_history()
    directions = _directions(history)

    cal = _load_calendar(cfg, today)
    forward_events = tuple({"time_label": e.time_label, "title": e.title} for e in cal.events)
    earnings = tuple({"ticker": e.ticker, "when": e.when} for e in cal.earnings if e.when == "bmo") \
        or tuple({"ticker": e.ticker, "when": e.when} for e in cal.earnings)
    # The degraded BANNER is reserved for stale CORE data or a failed model (spec §7.5).
    # The OPTIONAL "What to Watch" calendar is non-core: when it fails we show an honest
    # per-section note (calendar_note) instead of tripping the whole-brief banner.
    degraded = report.degraded
    calendar_note = _CALENDAR_DEGRADED_NOTE if cal.degraded else ""
    if cal.degraded:
        # Honest note only; does NOT trip the banner. The HTTP-status reason is
        # logged by sources/calendar.py for diagnosis (e.g. a 402/403 free-tier wall).
        print("  calendar: optional events feed unavailable (see calendar log); "
              "noting in What to Watch, banner unaffected")

    # Glance "why" is a SHORT direction/quiet tag, not the full causal sentence
    # (structure fix #4 — the full read lives once in the body section).
    glance_tags = {sid: _glance_tag(sid, history, directions) for sid, _, _ in vm._GLANCE_SPEC}
    glance_rows = vm.build_glance_rows(report.fields, glance_tags, directions=directions)

    # The four text rows below the figure rows (structure fix #2).
    text_rows = (
        ("Today's events", _events_summary(cal)),
        ("Earnings (pre-open)", _earnings_summary(cal)),
        ("Washington", _first_sentence(prose_by_section.get("washington", "")) or
            "No market-moving policy news flagged."),
        ("Bottom line", _bottom_line(degraded, diff_line)),
    )

    # Per-section citations from the validated narrative (item 1); inline HTML charts.
    cited_by_section = {
        sid: res.cited_sources for sid, res in (narrative_results or {}).items()
    }
    hbars, hbar_maxabs = vm.build_hbars(_index_changes(history))
    sparklines = vm.build_sparklines(_watchlist_history(cfg, history))

    # Per-section session/week/month stat tables (redesign "Visuals + macro").
    # Values come from the freshly-pulled fields, the trailing windows from history.
    stat_values = {k: (f.value if f and f.is_usable else None)
                   for k, f in report.fields.items()}
    stat_tables = vm.build_stat_tables(stat_values, history)
    # Monthly/administered macro readings (CPI/PCE/Fed funds) shown as a current-level
    # backdrop strip, not in the change table (a daily delta is meaningless for them).
    macro_strips = vm.build_macro_strips(stat_values)

    favicon_tickers = _favicon_tickers(cfg)

    # Per-stock tables / sparklines / "why" notes for Watchlist + Movers, built from
    # the best-effort stock pull + the spec §7 movers selection. Empty when offline
    # or the pull failed (the sections then show their honest quiet line).
    stock_quotes = stock_quotes or {}
    watch_order = cfg.get("watchlist") or []
    movers_order = [m.ticker for m in movers_sel.movers] if movers_sel else []
    stock_tables = {
        "watchlist": vm.build_stock_table(watch_order, stock_quotes),
        "movers": vm.build_stock_table(movers_order, stock_quotes),
    }
    stock_sparklines = {
        "watchlist": vm.build_stock_sparklines(watch_order, stock_quotes),
    }
    stock_notes = {
        "watchlist": vm.build_stock_notes(watch_order, narrative_results or {}),
        "movers": vm.build_stock_notes(movers_order, narrative_results or {}),
    }

    sections = vm.build_sections(
        order, prose_by_section,
        top_story_id=top_story_id,
        favicon_tickers=favicon_tickers,
        cited_by_section=cited_by_section,
        section_charts=section_charts,
        stat_tables=stat_tables,
        macro_strips=macro_strips,
        stock_tables=stock_tables,
        stock_sparklines=stock_sparklines,
        stock_notes=stock_notes,
        hbars=hbars,
        hbar_maxabs=hbar_maxabs,
        sparklines=sparklines,
    )

    return vm.BriefView(
        date_label=_long_date(today),
        send_label=f"Sent {live_label}",
        degraded=degraded,
        diff_line=diff_line,
        glance_rows=glance_rows,
        text_rows=text_rows,
        sections=sections,
        live_label=live_label,
        live_figures=(),  # populated once a live pre-market pull is wired (best-effort)
        forward_events=forward_events,
        earnings=earnings,
        calendar_note=calendar_note,
        chart_cids=tuple(c["cid"] for c in section_charts.values()),
    )


def _directions(history: dict[str, list[float]]) -> dict[str, str]:
    """Per-metric settled direction (up/down/flat) from the last two closes."""
    out: dict[str, str] = {}
    for key, hist in history.items():
        if len(hist) >= 2 and hist[-1] is not None and hist[-2] is not None:
            delta = hist[-1] - hist[-2]
            out[key] = "up" if delta > 0 else ("down" if delta < 0 else "flat")
    return out


# Short, scannable At-a-Glance tags by section (no cause, just the read).
_GLANCE_TAG_KEY: dict[str, str] = {
    "us_equities": "sp500", "rates_and_dollar": "ust10y",
    "commodities": "wti", "crypto": "btc", "volatility_breadth": "vix",
}


def _glance_tag(section_id: str, history: dict[str, list[float]], directions: dict[str, str]) -> str:
    """A short glance tag carrying the week/month context (structure fix #4).

    The session move is already visible in the figure color, so the tag adds the
    trailing context instead of repeating it: e.g. "Up 1.8% on the week". Falls
    back to a plain session direction when no window is computable.
    """
    from engine import context as ctx_mod

    key = _GLANCE_TAG_KEY.get(section_id)
    if not key:
        return "Quiet"
    ctx = ctx_mod.time_context(history.get(key, []), key)
    clause = ctx_mod.context_clause(ctx, key)
    if clause:
        # clause looks like ", up 1.8% on the week and 4.0% on the month"; trim the
        # leading comma+space and capitalize for a tidy tag.
        tag = clause[2:]
        return tag[0].upper() + tag[1:]
    direction = directions.get(key)
    if direction == "up":
        return "Higher on the session"
    if direction == "down":
        return "Lower on the session"
    if direction == "flat":
        return "Little changed"
    return "Quiet"


def _watchlist_history(cfg, history: dict[str, list[float]]) -> dict[str, list[float]]:
    """Watchlist ticker -> recent close series for sparklines.

    Only the metrics we already track in state have history; watchlist tickers are
    arbitrary symbols, so sparklines are drawn only for those that coincide with a
    tracked metric. A watchlist with no tracked overlap simply draws no sparkline.
    """
    watchlist = cfg.get("watchlist", []) or []
    out: dict[str, list[float]] = {}
    for ticker in watchlist:
        key = ticker.lower()
        if key in history and history[key]:
            out[ticker] = history[key]
    return out


def _build_charts(cfg, report) -> dict[str, charts_mod.Chart]:
    """Build the enabled default-on PNG charts, keyed by their owning section.

    The index daily-change bar and watchlist sparklines are now inline HTML (drawn
    in the template, never blocked), so only the yield curve (rates) and the WTI
    trend (commodities) remain PNGs. Each builder returns None on thin data and is
    simply skipped; a chart is never forced. History is shared across builders.
    """
    flags = cfg.get("charts", {}) or {}
    history = _state_history()
    built: dict[str, charts_mod.Chart] = {}

    dates = _state_history_dates()
    if flags.get("yield_curve"):
        chart = charts_mod.ten_year_trend(
            ten_year_history=history.get("ust10y", []),
            ten_year_dates=dates.get("ust10y", []),
        )
        if chart:
            built["rates_and_dollar"] = chart
    if flags.get("oil_trend"):
        chart = charts_mod.commodities_normalized(
            {k: history.get(k, []) for k in ("wti", "gold", "copper")},
            dates={k: dates.get(k, []) for k in ("wti", "gold", "copper")},
        )
        if chart:
            built["commodities"] = chart
    return built


def _state_history_dates() -> dict[str, list[str]]:
    """Per-metric ISO dates parallel to history, for dated chart axes. {} if none."""
    try:
        st = state_mod.load_state()
    except (FileNotFoundError, ValueError):
        return {}
    if st.missing:
        return {}
    from engine.metrics import METRIC_KEYS
    return {k: st.history_dates(k) for k in METRIC_KEYS}


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
    """Per-index WEEK %-change for the inline index bars.

    Week rather than daily: the daily move is already in the At-a-Glance figures
    and was near-flat in early sends, so daily bars were redundant and low-signal.
    The week view shows how the indices are tracking over the week (the new time
    context), which the glance does not. Falls back to the daily change when a full
    week of history is not yet available.
    """
    from engine import context as ctx_mod

    labels = {"sp500": "S&P 500", "nasdaq": "Nasdaq", "dow": "Dow", "russell": "Russell"}
    out: dict[str, float] = {}
    for key, label in labels.items():
        hist = history.get(key, [])
        ctx = ctx_mod.time_context(hist, key)
        if ctx.week_change is not None:
            out[label] = ctx.week_change
        elif len(hist) >= 2 and hist[-2]:
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


def _commit_state(*, send: bool, today: date | None = None, fields=None, stock_quotes=None) -> None:
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
    _append_stock_history(st, stock_quotes or {}, today or date.today())
    if fields:
        today_iso = (today or date.today()).isoformat()
        for key, field in fields.items():
            if not field.is_usable:
                continue
            # Seed a metric entry for any key not yet in an older state file, so the
            # macro additions (copper, inflation, policy rate, credit spread) begin
            # accruing history on their first real send (backward-compatible bump).
            if key not in st.data["metrics"]:
                st.data["metrics"][key] = state_mod._empty_metric(key)
            metric = st.data["metrics"][key]
            hist = list(metric.get("history", []))
            hist.append(field.value)
            metric["history"] = hist
            # Stamp today's date in lockstep so every close carries its true date
            # going forward (the chart x-axis is dated from real data, not inferred).
            # Backfill the gap with the seed if dates lag history.
            dates = list(metric.get("history_dates", []))
            while len(dates) < len(hist) - 1:
                dates.append("")   # unknown older dates (pre-schema closes)
            dates.append(today_iso)
            metric["history_dates"] = dates
            metric["prev_close"] = metric.get("close")
            metric["close"] = field.value
    st.data["last_sent_date"] = (today or date.today()).isoformat()
    st.data["sent_today"] = True
    state_mod.save_state(st)
    state_mod.commit_state_back()
    print("  state: written + commit-back attempted")


def _append_stock_history(st, stock_quotes: dict, today: date) -> None:
    """Append today's close/date/volume per pulled stock into the state's stocks map.

    Mirrors the metric-history append: seeds a stock entry if new (so a freshly
    added watchlist/movers ticker starts accruing history on its first real send),
    appends today's close + ISO date in lockstep, and stamps prev_close / close /
    volume / change_pct. A ticker with no usable close is skipped. save_state trims
    each stock history to STOCK_HISTORY_KEEP.
    """
    if not stock_quotes:
        return
    today_iso = today.isoformat()
    for ticker, quote in stock_quotes.items():
        if quote.close is None:
            continue
        state_mod.seed_stock_state(st.data, ticker)
        entry = st.data["stocks"][ticker]
        hist = list(entry.get("history", []))
        hist.append(quote.close)
        entry["history"] = hist
        dates = list(entry.get("history_dates", []))
        while len(dates) < len(hist) - 1:
            dates.append("")
        dates.append(today_iso)
        entry["history_dates"] = dates
        entry["prev_close"] = entry.get("close")
        entry["close"] = quote.close
        entry["volume"] = quote.volume
        entry["change_pct"] = quote.change_pct


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
