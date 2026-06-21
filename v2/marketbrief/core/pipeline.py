from __future__ import annotations
from datetime import datetime
from marketbrief.core.context import BriefContext
from marketbrief.core.models import SourceResult
from marketbrief.core.enums import SourceHealth, Verdict
from marketbrief.core.isolation import run_isolated
from marketbrief.core.registry import discover_sources, discover_sections
from marketbrief.core.health import assess
from marketbrief.fetch.resolver import resolve_fields
from marketbrief.sources.rss_source import RssSource
from marketbrief.compute.derive import derive_numbers
from marketbrief.compute.movers import compute_movers
from marketbrief.fetch.universe import fetch_universe_closes
from marketbrief.match.scorer import match_sections
from marketbrief.narrate.narrator import narrate
from marketbrief.narrate.client import build_client
from marketbrief.narrate.chain import run_chain, TagOnlyCauseCheck
from marketbrief.narrate.number_check import NumberCheck
from marketbrief.narrate.entailment import EntailmentCheck
from marketbrief.narrate.templated import templated_why
from marketbrief.assemble.diff_line import build_diff_line
from marketbrief.assemble.glance import build_glance_rows
from marketbrief.assemble.topstory import order_sections
from marketbrief.assemble.fence import build_live_snapshot
from marketbrief.assemble.brief_view import build_brief_view
from marketbrief.render.chart_set import build_charts


def _fetch(ctx: BriefContext, sources: list) -> BriefContext:
    facts: dict[str, SourceResult] = {}
    for src in sources:
        fallback = SourceResult(name=src.name, health=SourceHealth.FAILED)
        result, err = run_isolated(f"source:{src.name}", lambda src=src: src.fetch(ctx), fallback)
        if err is not None:
            result = SourceResult(name=src.name, health=SourceHealth.FAILED, error=err)
        facts[src.name] = result
    return ctx.with_updates(facts=facts)


def _resolve(ctx: BriefContext) -> BriefContext:
    return ctx.with_updates(resolved_fields=resolve_fields(ctx.facts, ctx.config))


def _fetch_news(ctx: BriefContext, news_source) -> BriefContext:
    result, err = run_isolated("news:rss", lambda: news_source.fetch_news(ctx), None)
    articles = result.articles if result is not None else []
    return ctx.with_updates(articles=articles)


def _assess(ctx: BriefContext) -> BriefContext:
    report = assess(
        ctx.resolved_fields,
        degraded_stale_threshold=ctx.config.resilience.degraded_stale_threshold,
        hard_floor_missing_threshold=ctx.config.resilience.hard_floor_missing_threshold,
    )
    return ctx.with_updates(health=report)


def _compute(ctx: BriefContext, universe_downloader=None) -> BriefContext:
    numbers = derive_numbers(ctx.resolved_fields, ctx.config)
    # Movers board: fetch universe closes (isolated, offline-safe) and rank in
    # Python. Empty/thin/offline -> a board with no rows, so Movers degrades quiet.
    closes, _err = run_isolated(
        "compute:movers_universe",
        lambda: fetch_universe_closes(ctx.config.movers_universe, downloader=universe_downloader),
        {},
    )
    board = compute_movers(closes or {})
    return ctx.with_updates(numbers=numbers, mover_board=board)


def _narrate(ctx: BriefContext, client) -> BriefContext:
    matched = match_sections(ctx.articles, ctx.config)
    narration = narrate(ctx.numbers, matched, client=client, config=ctx.config.narrate)
    validators = [TagOnlyCauseCheck(), NumberCheck(), EntailmentCheck(client, ctx.config.narrate)]
    judged: dict = {}
    all_causes = []
    for sid, why in narration.items():
        new_causes = [run_chain(c, ctx, validators) for c in why.causes]
        stripped = any(c.verdict == Verdict.STRIP for c in new_causes)
        if stripped:
            judged[sid] = templated_why(sid, ctx.numbers).model_copy(
                update={"causes": new_causes})
        else:
            judged[sid] = why.model_copy(update={
                "causes": new_causes,
                "degraded": why.degraded,
            })
        all_causes.extend(new_causes)
    return ctx.with_updates(narration=judged, causes=all_causes)


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
    png_by_cid, chartrefs_by_section_id = build_charts(ctx)
    enriched = [
        sec.model_copy(update={"charts": chartrefs_by_section_id.get(sec.id, [])})
        for sec in ordered
    ]
    view = build_brief_view(ctx, enriched, glance, diff, live)
    view = view.model_copy(update={"png_by_cid": png_by_cid})
    return ctx.with_updates(sections=enriched, brief_view=view)


def run_pipeline(ctx: BriefContext, *, sources: list | None = None,
                 sections: list | None = None, news_source=None,
                 narration_client=None, universe_downloader=None) -> BriefContext:
    sources = discover_sources() if sources is None else sources
    sections = discover_sections() if sections is None else sections
    news_source = RssSource() if news_source is None else news_source
    client = build_client() if narration_client is None else narration_client
    ctx = _fetch(ctx, sources)
    ctx = _resolve(ctx)
    ctx = _fetch_news(ctx, news_source)
    ctx = _assess(ctx)
    ctx = _compute(ctx, universe_downloader)
    ctx = _narrate(ctx, client)
    ctx = _assemble(ctx, sections)
    return ctx
