import os
from marketbrief.narrate.client import build_client


def test_build_client_returns_none_when_offline(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    assert build_client() is None


def test_build_client_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert build_client() is None
