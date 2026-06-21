"""The narrator: ONE constrained Claude call over the whole picture (spec ss5.6).

Injectable client (None when offline / no key). On any failure or offline, returns
templated lines so the brief never blocks. On success, returns one NarratedWhy per
section, each carrying a Cause when the model tagged one. Numbers are validated
downstream by the validator chain; the narrator does not inspect them."""
from __future__ import annotations
from marketbrief.core.models import ComputedNumbers, NarratedWhy, Cause
from marketbrief.core.isolation import run_isolated
from marketbrief.narrate.prompt import SYSTEM_PROMPT, SECTION_SCHEMA, build_user
from marketbrief.narrate.templated import templated_all


def narrate(numbers: ComputedNumbers, matched, *, client, config) -> dict[str, NarratedWhy]:
    if client is None:
        return templated_all(numbers)

    user = build_user(numbers, matched)
    payload, err = run_isolated(
        "narrate:sonnet",
        lambda: client.parse(
            model=config.model, system=SYSTEM_PROMPT, user=user,
            schema=SECTION_SCHEMA["schema"], max_tokens=config.max_tokens,
        ),
        None,
    )
    if payload is None or not isinstance(payload, dict):
        return templated_all(numbers)

    out: dict[str, NarratedWhy] = {}
    for sec in payload.get("sections", []):
        sid = sec.get("section_id")
        if not sid:
            continue
        causes: list[Cause] = []
        if sec.get("cause") and sec.get("cause_source_id"):
            causes.append(Cause(claim=sec.get("prose", ""),
                                cause_source_id=sec["cause_source_id"]))
        out[sid] = NarratedWhy(
            section_id=sid, text=sec.get("prose", ""),
            causes=causes, degraded=False,
        )
    return out
