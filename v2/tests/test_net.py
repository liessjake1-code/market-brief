import os
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT


def test_request_timeout_is_set():
    assert REQUEST_TIMEOUT == 15


def test_is_offline_true_when_env_set(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")
    assert is_offline() is True


def test_is_offline_false_when_unset(monkeypatch):
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)
    assert is_offline() is False


def test_is_offline_accepts_true_string(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "true")
    assert is_offline() is True
