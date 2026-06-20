from __future__ import annotations

import re
from dataclasses import dataclass, field

# Numeric token: optional $, digits with optional thousands separators and
# decimals, optional trailing %, "bps", "bp", or "k"/"M". Captures sign.
_NUMBER_RE = re.compile(
    r"""
    (?<![\w.])            # not mid-identifier
    (?P<sign>[-+]?)
    \$?
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s?
    (?P<unit>%|bps|bp|basis\ points)?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Whitelist patterns skipped entirely (spec §5.6 / Part 4.4 step 2).
_CLOCK_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})\b",
    re.IGNORECASE,
)
# Spelled-out ordinals ("fifth straight session") and digit ordinals ("5th").
_ORDINAL_WORDS = (
    "first second third fourth fifth sixth seventh eighth ninth tenth "
    "eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth "
    "eighteenth nineteenth twentieth"
).split()
_ORDINAL_DIGIT_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)

# Source-id references the model is instructed to cite inline, e.g. "WSJ (wsj-39)",
# "CNBC (cnbc-11)", "the Fed (fed-2)". The trailing digit is an article index, not
# a factual market number; left in, "wsj-39" leaks "39" into the number check and
# wrongly rejects good prose (the 2026-06-18 degrade). Strip the whole token.
_SOURCE_ID_RE = re.compile(r"\b(?:cnbc|mw|fed|wsj|ft|rss)-\d+\b", re.IGNORECASE)
# Bare 4-digit years (2024-2030); a calendar year is not a market figure to verify.
_YEAR_RE = re.compile(r"\b20[2-3]\d\b")

# Instrument names that embed digits are domain terminology, not factual claims,
# and must not be treated as numbers to verify. The model will routinely write
# "the 10-year", "the 2s10s spread", "S&P 500", "Russell 2000". These are
# evergreen names (like dates and ordinals), so they are whitelisted before
# extraction. Order matters: strip the most specific first.
_INSTRUMENT_RE = re.compile(
    r"""
    \b(?:
        2s10s | 2s\ 10s |                       # the 2s10s spread
        \d{1,3}-year | \d{1,3}\ year |          # the 10-year, 2-year, 30-year
        S&P\s?500 | Russell\s?2000 | Nasdaq\s?100 |
        Dow\ 30 | VIX
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

DEFAULT_TOLERANCE_PCT = 0.05   # ±0.05 for percentages (config number_tolerance_pct)
PRICE_TOLERANCE_ABS = 0.75     # small absolute band for an approximated price
BPS_TOLERANCE = 1.0            # ±1 bp


@dataclass
class ValidationResult:
    ok: bool
    rejected: list[str] = field(default_factory=list)   # offending tokens
    checked: list[str] = field(default_factory=list)


def _strip_whitelisted(prose: str) -> str:
    """Blank out non-factual numeric tokens before extraction.

    Order: instrument names first (so "10-year" goes before the bare-number rule
    can see "10"), then clock times, dates, and digit-ordinals.
    """
    prose = _SOURCE_ID_RE.sub(" ", prose)   # strip "wsj-39" before its digits are seen
    prose = _INSTRUMENT_RE.sub(" ", prose)
    prose = _CLOCK_RE.sub(" ", prose)
    prose = _DATE_RE.sub(" ", prose)
    prose = _YEAR_RE.sub(" ", prose)
    prose = _ORDINAL_DIGIT_RE.sub(" ", prose)
    return prose


@dataclass(frozen=True)
class _Token:
    raw: str
    value: float
    unit: str   # "pct" | "bps" | "plain"


def extract_numbers(prose: str) -> list[_Token]:
    cleaned = _strip_whitelisted(prose)
    tokens: list[_Token] = []
    for m in _NUMBER_RE.finditer(cleaned):
        raw = m.group(0).strip()
        num = m.group("num").replace(",", "")
        try:
            value = float(num)
        except ValueError:
            continue
        if m.group("sign") == "-":
            value = -value
        unit_raw = (m.group("unit") or "").lower()
        if unit_raw == "%":
            unit = "pct"
        elif unit_raw in ("bps", "bp", "basis points"):
            unit = "bps"
        else:
            unit = "plain"
        tokens.append(_Token(raw=raw, value=value, unit=unit))
    return tokens


def _matches_any(token: _Token, inputs: list[float], *, tolerance_pct: float) -> bool:
    """Is the token consistent with any input within its tolerance band?"""
    for candidate in inputs:
        if token.unit == "bps":
            if abs(abs(token.value) - abs(candidate)) <= BPS_TOLERANCE:
                return True
            continue
        if token.unit == "pct":
            if abs(abs(token.value) - abs(candidate)) <= tolerance_pct + 1e-9:
                return True
            # also accept exact-ish percentage rounding to one decimal
            if round(abs(token.value), 1) == round(abs(candidate), 1):
                return True
            continue
        # plain number / price: relative band OR small absolute band.
        if candidate != 0 and abs(token.value - candidate) / abs(candidate) <= 0.01:
            return True
        if abs(token.value - candidate) <= PRICE_TOLERANCE_ABS:
            return True
    return False


def validate_prose(
    prose: str,
    input_numbers: list[float],
    *,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> ValidationResult:
    """Reject prose containing any number not consistent with the input set.

    `input_numbers` MUST be the full computed set including derived figures
    (weekly sums, the 2s10s spread, index gaps); a derived figure absent from it
    is treated as invented and rejected (spec §5.6 step 1 + step 6).
    """
    inputs = [abs(n) for n in input_numbers] + list(input_numbers)
    tokens = extract_numbers(prose)
    rejected: list[str] = []
    checked: list[str] = []
    for token in tokens:
        checked.append(token.raw)
        if not _matches_any(token, inputs, tolerance_pct=tolerance_pct):
            rejected.append(token.raw)
    return ValidationResult(ok=not rejected, rejected=rejected, checked=checked)


# --- v2 Validator wrapper -------------------------------------------------- #
from marketbrief.core.enums import Verdict


class NumberCheck:
    """A number in the claim inconsistent with the computed input set -> STRIP.

    Reads ctx.numbers.values (the same-day ComputedNumbers). The model is told to
    round and approximate, so this is a tolerant consistency check, not identity."""

    def judge(self, cause, ctx) -> Verdict:
        inputs = list(ctx.numbers.values.values())
        result = validate_prose(cause.claim, inputs)
        return Verdict.PASS if result.ok else Verdict.STRIP
