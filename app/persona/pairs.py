from datetime import datetime, timedelta

from pydantic import BaseModel

from app.ingest.models import Message
from app.persona.models import ReplyExample

BURST_GAP = timedelta(minutes=5)
CONTEXT_WINDOW = timedelta(hours=6)
MAX_REPLY_LINES = 6
MAX_CONTEXT_CHARS = 400


class Burst(BaseModel):
    """Consecutive messages from one sender, sent close together."""

    sender: str
    lines: list[str]
    start: datetime
    end: datetime


def to_bursts(messages: list[Message]) -> list[Burst]:
    bursts: list[Burst] = []
    for m in messages:
        last = bursts[-1] if bursts else None
        if last and last.sender == m.sender and m.ts - last.end <= BURST_GAP:
            last.lines.append(m.text)
            last.end = m.ts
        else:
            bursts.append(Burst(sender=m.sender, lines=[m.text], start=m.ts, end=m.ts))
    return bursts


def build_pairs(bursts: list[Burst], persona_sender: str) -> list[ReplyExample]:
    """(what others just said -> how the persona replied) for every persona burst
    that answers someone within CONTEXT_WINDOW."""
    pairs = []
    for i, burst in enumerate(bursts):
        if burst.sender != persona_sender or i == 0:
            continue
        prev = bursts[i - 1]
        if prev.sender == persona_sender or burst.start - prev.end > CONTEXT_WINDOW:
            continue
        context = "\n".join(prev.lines)[-MAX_CONTEXT_CHARS:]
        reply = "\n".join(burst.lines[:MAX_REPLY_LINES])
        pairs.append(ReplyExample(context=context, reply=reply))
    return pairs
