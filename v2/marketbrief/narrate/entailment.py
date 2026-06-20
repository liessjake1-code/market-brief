"""Entailment validator (NEW in v2): proves the cited article supports the claim.

Closes v1's tag-only gap (spec section 5.6: the tag check 'does not verify that the
article actually supports the cause'). Cheap Haiku call per surviving cause. Appended
AFTER the tag-only and number checks in the chain, so the worst verdict wins. Offline /
no client / no matching article -> PASS (deterministic checks already guarded the
cause). A throwing call is RAISED so run_chain's isolation maps it to STRIP (fail
closed).
"""
from __future__ import annotations
from marketbrief.core.enums import Verdict

_VERDICT_MAP = {"supports": Verdict.PASS, "weak": Verdict.HEDGE,
                "contradicts": Verdict.STRIP}

_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["verdict"],
    "properties": {"verdict": {"type": "string",
                               "enum": ["supports", "weak", "contradicts"]}},
}

_SYSTEM = (
    "You judge whether a news article supports a causal market claim. Answer with "
    "'supports' if the article clearly supports the claim, 'weak' if it is only "
    "loosely related or partial, and 'contradicts' if it is unrelated or contradicts "
    "the claim. Be strict: a tenuous match is 'weak', not 'supports'."
)


class EntailmentCheck:
    def __init__(self, client, config) -> None:
        self._client = client
        self._config = config

    def judge(self, cause, ctx) -> Verdict:
        if self._client is None or not cause.cause_source_id:
            return Verdict.PASS
        article = next((a for a in ctx.articles
                        if a.source_id == cause.cause_source_id), None)
        if article is None:
            return Verdict.PASS
        user = (f"Claim: {cause.claim}\n"
                f"Article title: {article.title}\n"
                f"Article summary: {article.summary}")
        result = self._client.parse(
            model=self._config.entailment_model, system=_SYSTEM, user=user,
            schema=_SCHEMA, max_tokens=16,
        )
        return _VERDICT_MAP.get(result.get("verdict"), Verdict.HEDGE)
