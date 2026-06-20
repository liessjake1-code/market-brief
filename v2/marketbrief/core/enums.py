from __future__ import annotations
from enum import Enum


class RunMode(str, Enum):
    SEND = "send"
    NO_SEND = "no_send"
    FULL = "full"


class SourceHealth(str, Enum):
    OK = "ok"
    STALE = "stale"
    FAILED = "failed"
    MISSING = "missing"


class Verdict(str, Enum):
    PASS = "pass"
    HEDGE = "hedge"
    STRIP = "strip"
