"""Local sanitization pipeline (privacy-and-guardrails.md §3). Runs before anything is
stored, embedded or sent to an LLM. Not yet implemented: NER for names that aren't
participants, and the LLM sensitive-topic classifier (stages 4b/5)."""

from collections import Counter

from pydantic import BaseModel

from app.guardrails.artifacts import drop_artifacts
from app.guardrails.pii import redact_pii
from app.guardrails.pseudonymize import Pseudonymizer
from app.ingest.models import Message


class SanitizationReport(BaseModel):
    messages_in: int
    messages_out: int
    artifacts_dropped: int
    pii: dict[str, int]
    participants_pseudonymized: int


def sanitize_chat(
    messages: list[Message], persona_sender: str
) -> tuple[list[Message], SanitizationReport]:
    """Keep the persona's name (and, in a 1:1 chat, the other person: the operator);
    pseudonymize everyone else; redact PII; drop WhatsApp artifacts."""
    senders = list(dict.fromkeys(m.sender for m in messages))
    keep = {persona_sender} | (set(senders) if len(senders) <= 2 else set())
    others = [s for s in senders if s not in keep]
    pseudo = Pseudonymizer(keep, others)

    kept, dropped = drop_artifacts(messages)
    pii: Counter[str] = Counter()
    clean = [
        Message(
            ts=m.ts,
            sender=pseudo.sender(m.sender),
            text=pseudo.text(redact_pii(m.text, pii)),
        )
        for m in kept
    ]
    report = SanitizationReport(
        messages_in=len(messages),
        messages_out=len(clean),
        artifacts_dropped=dropped,
        pii=dict(pii),
        participants_pseudonymized=len(others),
    )
    return clean, report
