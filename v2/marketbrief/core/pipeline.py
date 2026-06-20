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
