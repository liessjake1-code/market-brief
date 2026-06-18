"""Render a template variant against a realistic BriefView fixture, no pipeline.

Usage: uv run ... python design-preview/preview_fixture.py <template_path> <out_html>
Builds believable content (real-looking numbers, good prose, populated watchlist
and live zone, per-section citations, inline HTML charts) so design variants are
judged on realistic data, not placeholders. Mirrors the production BriefView so
the preview matches what the real pipeline renders.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import jinja2
from render import viewmodel as vm


def cell(label, value, direction="flat", url="https://finance.yahoo.com/quote/%5EGSPC"):
    return vm.FigureCell(label=label, value=value, url=url, direction=direction)


def build_view():
    glance_rows = (
        vm.GlanceRow("Markets", (
            cell("S&P", "6,431", "up"), cell("Nasdaq", "21,054", "up"),
            cell("Dow", "44,210", "down"), cell("Russell", "2,318", "down"),
        ), "Up 1.8% on the week and 4.0% on the month"),
        vm.GlanceRow("Rates and dollar", (
            cell("10Y", "4.43%", "up"), cell("2Y", "4.05%", "flat"), cell("DXY", "100.8", "up"),
        ), "Up 7 bps on the week"),
        vm.GlanceRow("Commodities", (
            cell("WTI", "74.05", "down"), cell("Gold", "4,247", "up"),
        ), "Down 2.0% on the week and 6.0% on the month"),
        vm.GlanceRow("Crypto", (
            cell("BTC", "62,636", "up"), cell("ETH", "1,687", "down"),
        ), "Up 3.1% on the week"),
        vm.GlanceRow("Volatility", (cell("VIX", "16.98", "down"),), "Down 9.0% on the week"),
    )
    text_rows = (
        ("Today's events", "Initial jobless claims, 7:30 CT; Fed's Williams speaks midday."),
        ("Earnings (pre-open)", "FedEx, Darden Restaurants before the bell."),
        ("Washington", "Tariff headlines quiet; shutdown deadline still three weeks out."),
        ("Bottom line", "Mild risk-on into data; rates the swing factor."),
    )

    hbars, hbar_maxabs = vm.build_hbars(
        {"S&P": 0.4, "Nasdaq": 0.7, "Dow": -0.3, "Russell": -1.2}
    )
    sparklines = vm.build_sparklines(
        {"SPCX": [3, 4, 4, 5, 6, 6, 7], "NVDA": [5, 5, 6, 6, 7, 8, 9]}
    )

    # Realistic histories so the section stat tables compute real session/week/month
    # changes (most-recent-last, ~22 sessions for a full month window).
    def ramp(start, step, n=22, jitter=0.0):
        out = []
        v = start
        for i in range(n):
            v = v + step + (jitter if i % 2 == 0 else -jitter)
            out.append(round(v, 4))
        return out

    histories = {
        "sp500": ramp(6180, 11.5), "nasdaq": ramp(20200, 39), "dow": ramp(44400, -9),
        "russell": ramp(2360, -2.0), "wti": ramp(80.0, -0.30, jitter=0.6),
        "gold": ramp(4010, 11), "copper": ramp(4.35, 0.012, jitter=0.02),
        "dxy": ramp(99.6, 0.055), "ust10y": ramp(4.30, 0.006, jitter=0.01),
        "ust2y": ramp(4.06, -0.0005, jitter=0.008), "btc": ramp(60800, 84),
        "eth": ramp(1720, -1.5), "vix": ramp(18.6, -0.08, jitter=0.2),
        "fed_funds": [5.33] * 22, "cpi_yoy": [3.4] * 18 + [3.2] * 4,
        "pce_yoy": [2.8] * 18 + [2.7] * 4, "hy_spread": ramp(3.20, -0.007, jitter=0.01),
    }
    values = {k: v[-1] for k, v in histories.items()}
    stat_tables = vm.build_stat_tables(values, histories)

    # NOTE: the prose + chart_takeaway strings below are DEMO fixture data only,
    # hand-written for a realistic preview. In production every figure is computed
    # in Python (engine.stats / render.charts takeaways); the model writes no number.
    def section(sid, prose, top=False, favicons=(), sources=(), chart=None):
        return vm.SectionView(
            section_id=sid, title=vm.SECTION_TITLES[sid], prose=prose,
            is_top_story=top, favicons=favicons, sources=sources,
            hbars=hbars if top else (), hbar_maxabs=hbar_maxabs if top else 1.0,
            sparklines=sparklines if sid == "watchlist" else (),
            chart_cid=(chart or {}).get("cid"),
            chart_caption=(chart or {}).get("caption", ""),
            chart_caption_url=(chart or {}).get("caption_url", ""),
            chart_takeaway=(chart or {}).get("takeaway", ""),
            stat_table=stat_tables.get(sid, ()),
        )

    movers_fav = (
        {"ticker": "NVDA", "url": "#", "favicon": "https://www.google.com/s2/favicons?domain=nvidia.com&sz=64"},
        {"ticker": "TSLA", "url": "#", "favicon": "https://www.google.com/s2/favicons?domain=tesla.com&sz=64"},
        {"ticker": "AMD", "url": "#", "favicon": None},
    )
    watch_fav = (
        {"ticker": "SPCX", "url": "#", "favicon": "https://www.google.com/s2/favicons?domain=spacex.com&sz=64"},
        {"ticker": "QUBT", "url": "#", "favicon": None},
        {"ticker": "TSLA", "url": "#", "favicon": "https://www.google.com/s2/favicons?domain=tesla.com&sz=64"},
        {"ticker": "NVDA", "url": "#", "favicon": "https://www.google.com/s2/favicons?domain=nvidia.com&sz=64"},
    )
    sections = (
        section("us_equities",
                "The S&P 500 added 0.4% to 6,431 as megacap tech carried the tape, but the "
                "Dow slipped and the Russell 2000 lagged by nearly a point, a classic narrow "
                "advance. Reuters tied the leadership to renewed AI capex optimism. Watch "
                "whether breadth confirms or the rally stays top-heavy into Friday's data.",
                top=True,
                sources=({"label": "Reuters: Wall St rises as AI optimism lifts megacaps",
                          "url": "https://www.reuters.com/markets/us/"},)),
        section("rates_and_dollar",
                "The 10-year backed up to 4.43%, up 7 bps on the week, after a soft 20-year "
                "auction drew weak demand (Bloomberg). The 2s10s steepened to +38 bps. Higher "
                "long-end yields are the headwind small caps just felt; the dollar firmed to 100.8.",
                sources=({"label": "Bloomberg: 20-year auction draws weak demand",
                          "url": "https://www.bloomberg.com/markets/rates-bonds"},),
                chart={"cid": "chart_rates", "caption": "Source: FRED (DGS10)",
                       "caption_url": "https://fred.stlouisfed.org/series/DGS10",
                       "takeaway": "The 10-year sits at 4.43%, up 7 bps on the week and near the top of its past-month range, so the long end remains the swing factor into the next data print."}),
        section("commodities",
                "WTI eased to $74.05, down about 2% on the week as builds outweighed the "
                "geopolitical bid; gold pushed to a record $4,247 on the same rate-cut hopes. "
                "Softer oil takes some pressure off the inflation read the Fed watches.",
                sources=({"label": "Reuters: Oil slips on US crude build",
                          "url": "https://www.reuters.com/business/energy/"},),
                chart={"cid": "chart_commodities", "caption": "Source: Yahoo Finance (CL=F, GC=F, HG=F)",
                       "caption_url": "https://finance.yahoo.com/chart/CL=F",
                       "takeaway": "Rebased to 100 a month ago, gold leads (+3.1%) while WTI lags (-6.0%) and copper is roughly flat, a defensive-metals tilt rather than a broad commodity bid."}),
        section("washington", "No market-moving policy news flagged this morning. The shutdown "
                "deadline is three weeks out and tariff headlines were quiet. No clear catalyst "
                "flagged. The long end is the swing factor into the next data print."),
        section("movers",
                "NVDA led the tape up 3.1% on the AI-capex headlines; TSLA gained 2.4% into "
                "its delivery update. AMD lagged the group, off 1.2%.", favicons=movers_fav),
        section("economic_data_scorecard", "No major economic releases on the board. The next "
                "scorecard print is Friday's claims. No clear catalyst flagged."),
        section("earnings_on_deck", "FedEx and Darden report before the open; both are demand bellwethers."),
        section("watchlist",
                "SPCX held its IPO gains; QUBT slipped on profit-taking; TSLA tracked the tape; "
                "NVDA led. No single-name catalyst beyond the broad AI bid.", favicons=watch_fav),
        section("crypto", "Bitcoin firmed to 62,636 while Ether slipped; risk appetite reads neutral-to-firm."),
        section("volatility_breadth", "VIX eased to 16.98. No hedging demand; nothing to read into it."),
    )

    live_figures = (
        cell("S&P fut", "+0.2%", "up"), cell("Nasdaq fut", "+0.3%", "up"),
        cell("10Y", "4.44%", "up"), cell("WTI", "73.90", "down"),
    )
    forward_events = (
        {"time_label": "7:30 CT", "title": "Initial jobless claims"},
        {"time_label": "11:00 CT", "title": "Fed's Williams speaks"},
        {"time_label": "—", "title": "20-year bond auction, 12:00 CT"},
    )
    earnings = ({"ticker": "FDX", "when": "amc"}, {"ticker": "DRI", "when": "bmo"})

    return vm.BriefView(
        date_label="Thursday, June 18, 2026",
        send_label="Sent 8:31 AM CT",
        degraded=False,
        diff_line="S&P set a new 20-day high; the Dow turned lower; small caps lagged a fifth straight session.",
        glance_rows=glance_rows,
        text_rows=text_rows,
        sections=sections,
        live_label="Pre-market as of 8:31 AM CT",
        live_figures=live_figures,
        forward_events=forward_events,
        earnings=earnings,
        chart_cids=(),
    )


def main():
    template_path = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    view = build_view()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        autoescape=jinja2.select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tmpl = env.get_template(template_path.name)
    html = tmpl.render(view=view, text_rows=view.text_rows)
    # For a BROWSER preview, cid: URLs don't resolve, so render the real WTI chart
    # and inline it as a data-URI so the screenshot shows the actual chart image.
    html = _inline_demo_chart(html)
    out.write_text(html)
    print("WROTE", out, len(html), "chars")


def _inline_demo_chart(html: str) -> str:
    """Render the real new charts and inline them as data-URIs for browser preview.

    cid: URLs only resolve in an email client, so for a headless-Chrome screenshot
    we render the actual rates + commodities charts and swap the cid refs.
    """
    import base64
    try:
        from render import charts
        dates = [f"2026-05-{d:02d}" for d in range(20, 32)] + \
                [f"2026-06-{d:02d}" for d in range(1, 11)]

        ten = [4.30 + 0.006 * i + (0.012 if i % 2 else -0.012) for i in range(22)]
        rates = charts.ten_year_trend(ten_year_history=ten, ten_year_dates=dates[:22])

        wti = [80.0 - 0.30 * i + (0.6 if i % 2 else -0.6) for i in range(22)]
        gold = [4010 + 11 * i for i in range(22)]
        copper = [4.35 + 0.012 * i + (0.02 if i % 2 else -0.02) for i in range(22)]
        commodities = charts.commodities_normalized(
            {"wti": wti, "gold": gold, "copper": copper},
            dates={k: dates[:22] for k in ("wti", "gold", "copper")},
        )

        for cid, chart in (("chart_rates", rates), ("chart_commodities", commodities)):
            if chart is None:
                continue
            b64 = base64.b64encode(chart.png).decode()
            html = html.replace(f"cid:{cid}", f"data:image/png;base64,{b64}")
        return html
    except Exception as exc:  # preview is best-effort
        print("  (chart inline skipped:", exc, ")")
        return html


if __name__ == "__main__":
    main()
