"""Fish Audio voices offered when creating a persona (verified with s2.1-pro, 2026-10-24).
Defaults are plain conversational library voices, deliberately not celebrity/character imitations."""

from typing import Literal

from pydantic import BaseModel


class VoiceOption(BaseModel):
    id: str  # Fish Audio reference_id
    name: str
    gender: Literal["female", "male"]
    language: str
    description: str


VOICES = [
    VoiceOption(
        id="933563129e564b19a115bedd57b7406a",
        name="Sarah",
        gender="female",
        language="English",
        description="young, conversational, soft",
    ),
    VoiceOption(
        id="b347db033a6549378b48d00acb0d06cd",
        name="Selene",
        gender="female",
        language="English",
        description="calm, gentle",
    ),
    VoiceOption(
        id="c5f56a6cc2ec4fa8920cb4c5889a3fb7",
        name="Slax",
        gender="male",
        language="English",
        description="clear, smooth",
    ),
    VoiceOption(
        id="711cf3ed00ab441a8f54a45058047b7a",
        name="Verity",
        gender="male",
        language="English",
        description="young, conversational, energetic",
    ),
    VoiceOption(
        id="4d7609058bd34213b1378b29efbde1f1",
        name="Girl Hindi",
        gender="female",
        language="Hindi",
        description="young, energetic, conversational",
    ),
    VoiceOption(
        id="528f686ef2154885b368dd4b93fb8728",
        name="Boy Hindi",
        gender="male",
        language="Hindi",
        description="expressive, energetic, conversational",
    ),
]

VOICES_BY_ID = {v.id: v for v in VOICES}
