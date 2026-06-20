from __future__ import annotations
from marketbrief.core.context import BriefContext
from marketbrief.core.models import SourceResult
from marketbrief.core.enums import SourceHealth, Verdict
from marketbrief.core.isolation import run_isolated
from marketbrief.core.registry import discover_sources, discover_sections
from marketbrief.core.health import assess
from marketbrief.fetch.resolver import resolve_fields
from marketbrief.sources.rss_source import RssSource
from marketbrief.compute.derive import derive_numbers
from marketbrief.match.scorer import match_sections
from marketbrief.narrate.narrator import narrate
from marketbrief.narrate.client import build_client
from marketbrief.narrate.chain import run_chain, TagOnlyCauseCheck
from marketbrief.narrate.number_check import NumberCheck
from marketbrief.narrate.entailment import EntailmentCheck
from marketbrief.narrate.templated import templated_why


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


def _compute(ctx: BriefContext) -> BriefContext:
    return ctx.with_updates(numbers=derive_numbers(ctx.resolved_fields, ctx.config))


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
    return ctx.with_updates(sections=sorted(built, key=lambda v: v.order))


def run_pipeline(ctx: BriefContext, *, sources: list | None = None,
                 sections: list | None = None, news_source=None,
                 narration_client=None) -> BriefContext:
    sources = discover_sources() if sources is None else sources
    sections = discover_sections() if sections is None else sections
    news_source = RssSource() if news_source is None else news_source
    client = build_client() if narration_client is None else narration_client
    ctx = _fetch(ctx, sources)
    ctx = _resolve(ctx)
    ctx = _fetch_news(ctx, news_source)
    ctx = _assess(ctx)
    ctx = _compute(ctx)
    ctx = _narrate(ctx, client)
    ctx = _assemble(ctx, sections)
    return ctx
