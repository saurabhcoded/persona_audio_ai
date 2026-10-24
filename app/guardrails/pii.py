"""Local regex PII redaction (privacy-and-guardrails.md §3.1). Placeholders keep sentence shape."""

import re
from collections import Counter


def _luhn(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()][::-1]
    if not 13 <= len(digits) <= 19:
        return False
    total = sum(digits[0::2]) + sum(sum(divmod(2 * d, 10)) for d in digits[1::2])
    return total % 10 == 0


# Order matters: UPI before EMAIL, CARD before PHONE/AADHAAR.
_UPI = re.compile(
    r"\b[\w.-]{2,}@(?:ok\w+|ybl|ibl|axl|apl|paytm|upi|sbi|icici|hdfcbank|axisbank|kotak|yesbank)\b",
    re.IGNORECASE,
)
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_PATTERNS = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("URL", re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)),
    (
        "AADHAAR",
        re.compile(r"(?<!\d)(?<!\d[ -])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)"),
    ),
    (
        "PHONE",
        re.compile(
            r"(?:\+91[\s-]?|\b0)?\b[6-9]\d{4}[\s-]?\d{5}\b|\+\d{1,3}[\s-]?\d[\d\s-]{7,13}\d"
        ),
    ),
    # Bank account numbers (9-18 digits) and any other long digit run left over.
    ("ACCOUNT", re.compile(r"(?<!\d)\d(?:[ -]?\d){8,17}(?![ -]?\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("OTP", re.compile(r"\b(?:otp|code|pin)\b\D{0,15}\b\d{4,8}\b", re.IGNORECASE)),
    (
        "SECRET",
        re.compile(r"\b(?:password|passwd|pwd)\b\s*(?:is|:|=|-)?\s*\S+", re.IGNORECASE),
    ),
]
PLACEHOLDERS = ["UPI", "CARD"] + [label for label, _ in _PATTERNS]


def redact_pii(text: str, counts: Counter[str] | None = None) -> str:
    counts = counts if counts is not None else Counter()

    def sub(label: str, pattern: re.Pattern, text: str) -> str:
        def repl(m: re.Match) -> str:
            counts[label] += 1
            return f"[{label}]"

        return pattern.sub(repl, text)

    text = sub("UPI", _UPI, text)

    def card(m: re.Match) -> str:
        if not _luhn(m.group()):
            return m.group()
        counts["CARD"] += 1
        return "[CARD]"

    text = _CARD.sub(card, text)
    for label, pattern in _PATTERNS:
        text = sub(label, pattern, text)
    return text


def find_pii(text: str) -> list[str]:
    """Labels of PII found in text (used by the output guard and privacy tests)."""
    counts: Counter[str] = Counter()
    redact_pii(text, counts)
    return list(counts)
