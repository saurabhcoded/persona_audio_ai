import re

from app.guardrails.pii import PLACEHOLDERS, redact_pii

_PLACEHOLDER = re.compile(
    r"\[(?:" + "|".join(PLACEHOLDERS) + r"|PRIVATE)\]|\b(?:Person|Contact)_\d+\b"
)
_SPACES = re.compile(r"[ \t]{2,}")


def guard_reply(text: str) -> str:
    """Reply-time guard (FR-GRD-08): remove any PII the model produced and any
    placeholder/pseudonym it copied from the sanitized examples."""
    text = _PLACEHOLDER.sub("", redact_pii(text))
    return "\n".join(
        cleaned
        for line in text.splitlines()
        if (cleaned := _SPACES.sub(" ", line).strip())
    )
