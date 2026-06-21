from __future__ import annotations
from enum import Enum


class RunMode(str, Enum):
    SEND = "send"
    NO_SEND = "no_send"


class SourceHealth(str, Enum):
    OK = "ok"
    STALE = "stale"
    FAILED = "failed"
    MISSING = "missing"


class Verdict(str, Enum):
    PASS = "pass"
    HEDGE = "hedge"
    STRIP = "strip"


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class ChartKind(str, Enum):
    BAR = "bar"
    LINE = "line"
    CURVE = "curve"
    SPARK = "spark"
