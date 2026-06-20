"""System prompt + per-section bundle assembly (spec ss5.6 step 4-5).

Hands the model the computed numbers and the 2-3 matched articles per section. The
model extracts reporters' explicit causes, then writes using only those reasons plus
the supplied numbers, rounding and never introducing a number. Structured output
(SECTION_SCHEMA) keeps each claim tagged to its cause_source_id."""
from __future__ import annotations
import json
from marketbrief.core.models import ComputedNumbers
from marketbrief.match.scorer import ScoredArticle

SYSTEM_PROMPT = (
    "You write the 'why' for a daily market brief. You receive computed numbers and "
    "2 to 3 matched news articles per section. Rules, all mandatory:\n"
    "1. Never introduce or alter a number. Use only the numbers supplied. Round and "
    "approximate (say 'about 76 dollars', never '76.23').\n"
    "2. Every causal claim must cite a supplied article by its cause_source_id. If no "
    "article supports a cause, write 'no clear catalyst' and leave cause null. Never "
    "manufacture a cause.\n"
    "3. Plain declarative prose. No em dashes, no emojis.\n"
    "4. Emit structured JSON: one entry per section with section_id, prose, cause "
    "(short phrase or null), cause_source_id (or null), and confidence (low/medium/high)."
)

SECTION_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["sections"],
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["section_id", "prose", "cause",
                                 "cause_source_id", "confidence"],
                    "properties": {
                        "section_id": {"type": "string"},
                        "prose": {"type": "string"},
                        "cause": {"type": ["string", "null"]},
                        "cause_source_id": {"type": ["string", "null"]},
                        "confidence": {"type": "string",
                                       "enum": ["low", "medium", "high"]},
                    },
                },
            }
        },
    },
}


def build_user(numbers: ComputedNumbers,
               matched: dict[str, list[ScoredArticle]]) -> str:
    bundle = {
        "numbers": numbers.values,
        "sections": {
            sid: [
                {"cause_source_id": s.article.source_id,
                 "title": s.article.title,
                 "summary": s.article.summary,
                 "match_score": round(s.match_score, 3)}
                for s in scored
            ]
            for sid, scored in matched.items()
        },
    }
    return json.dumps(bundle, sort_keys=True)
