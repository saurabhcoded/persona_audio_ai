from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.speech.cues import EmojiCue


class ReplyExample(BaseModel):
    context: str  # what the other person said
    reply: str  # how the persona actually replied (newline = separate bubbles)


class Persona(BaseModel):
    id: str
    name: str
    tagline: str = ""
    source: Literal["demo", "chat"] = "chat"
    status: Literal["building", "ready", "failed"] = "ready"
    error: str | None = None
    created_at: datetime | None = None
    consent_basis: str | None = None
    sender_name: str | None = None  # the persona's name in the chat export
    card: str = ""  # persona card (LLM-extracted for chat personas)
    style: str = ""  # hard style constraints from StyleStats
    stats: dict | None = None
    report: dict | None = None  # SanitizationReport (counts only)
    # Static examples (demo persona); chat personas retrieve theirs from the pair index.
    examples: list[ReplyExample] = []
    emoji_map: dict[str, EmojiCue] = {}
    voice_id: str | None = None
