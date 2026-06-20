"""Anthropic client seam: the only place the SDK is touched.

The narrator and the entailment validator depend on the NarrationClient protocol,
so both are injectable and offline-gated. build_client() returns None when offline
or when no API key / SDK is available, which the callers treat as 'degrade to
templated'. Tests inject a fake that satisfies the protocol; they never hit the API."""
from __future__ import annotations
import json
import os
from typing import Protocol

from marketbrief.fetch.net import is_offline


class NarrationClient(Protocol):
    def parse(self, *, model: str, system: str, user: str,
              schema: dict, max_tokens: int) -> dict: ...


class AnthropicClient:
    """Real wrapper. Uses structured outputs (output_config.format) on messages.create.

    Returns the parsed JSON object. Numbers are validated downstream; this layer
    does not inspect content."""

    def __init__(self, api_key: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def parse(self, *, model: str, system: str, user: str,
              schema: dict, max_tokens: int) -> dict:
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)


def build_client() -> NarrationClient | None:
    if is_offline():
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        return AnthropicClient(key)
    except Exception:  # noqa: BLE001 - SDK import/init failure -> degrade
        return None
