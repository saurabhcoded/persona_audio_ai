from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.speech.cues import EmojiCue


class ReplyExample(BaseModel):
    context: str  # what the other person said
    reply: str  # how the persona actually replied (newline = separate bubbles)


class ShortForm(BaseModel):
    """A chat short form the persona uses ("r" -> "are", "h" -> "hai")."""

    short: str = Field(min_length=1, max_length=15)
    full: str = Field(min_length=1, max_length=60)
    count: int = 0  # times the persona used it (0 = added by hand)
    example: str = ""  # one real (sanitized) message using it
    enabled: bool = True


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
    shortforms: list[ShortForm] = []
    expand_shortforms_in_speech: bool = True  # say "are you", not "r u"
    expand_shortforms_in_text: bool = (
        False  # keep their texting style on screen by default
    )
