"""Fish Audio voices offered for personas: a built-in catalog (verified with s2.1-pro,
2026-10-24) plus custom voices the user adds by Fish voice ID (DATA_DIR/voices.json).
Defaults are plain conversational library voices, deliberately not celebrity/character imitations."""

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

VOICE_ID = re.compile(r"^[0-9a-f]{32}$")
LANGUAGES = {
    "hi": "Hindi", "en": "English", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "es": "Spanish", "fr": "French", "de": "German", "ar": "Arabic", "ru": "Russian",
    "pt": "Portuguese", "it": "Italian", "nl": "Dutch", "pl": "Polish", "bn": "Bengali",
    "ta": "Tamil", "te": "Telugu", "mr": "Marathi", "ur": "Urdu", "pa": "Punjabi",
}  # fmt: skip


class VoiceOption(BaseModel):
    id: str  # Fish Audio reference_id
    name: str
    gender: Literal["female", "male", "other"]
    language: str
    description: str
    custom: bool = False
    added_at: datetime | None = None


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


def voice_from_fish(voice, name: str | None = None) -> VoiceOption:
    """VoiceOption from a fishaudio Voice model (title, tags, languages)."""
    tags = [t.lower() for t in (voice.tags or [])]
    gender = "female" if "female" in tags else "male" if "male" in tags else "other"
    langs = [LANGUAGES.get(code, code) for code in (voice.languages or [])]
    descriptive = [t for t in voice.tags or [] if t.lower() not in {"male", "female"}]
    return VoiceOption(
        id=voice.id,
        name=(name or voice.title or "Custom voice").strip()[:60],
        gender=gender,
        language=", ".join(langs) or "Unknown",
        description=", ".join(descriptive[:3]) or "custom voice",
        custom=True,
        added_at=datetime.now(),
    )


class VoiceLibrary:
    """Built-in catalog + the user's custom voices."""

    def __init__(self, path: Path):
        self.path = path

    def _custom(self) -> list[VoiceOption]:
        if not self.path.is_file():
            return []
        return [
            VoiceOption.model_validate(v) for v in json.loads(self.path.read_text())
        ]

    def _write(self, voices: list[VoiceOption]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([v.model_dump(mode="json") for v in voices], indent=2)
        )
        tmp.replace(self.path)

    def all(self) -> list[VoiceOption]:
        return VOICES + self._custom()

    def get(self, voice_id: str) -> VoiceOption | None:
        return next((v for v in self.all() if v.id == voice_id), None)

    def add(self, voice: VoiceOption) -> VoiceOption:
        self._write([v for v in self._custom() if v.id != voice.id] + [voice])
        return voice

    def remove(self, voice_id: str) -> bool:
        custom = self._custom()
        kept = [v for v in custom if v.id != voice_id]
        if len(kept) == len(custom):
            return False
        self._write(kept)
        return True


@lru_cache
def _library(data_dir: str) -> VoiceLibrary:
    return VoiceLibrary(Path(data_dir) / "voices.json")


def get_voice_library(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VoiceLibrary:
    return _library(settings.data_dir)


VoiceLibraryDep = Annotated[VoiceLibrary, Depends(get_voice_library)]
