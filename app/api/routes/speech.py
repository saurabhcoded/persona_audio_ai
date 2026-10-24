from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.speech.cues import validate_cues
from app.speech.tts import TTSDep
from app.speech.voices import VOICES, VOICES_BY_ID, VoiceOption
from app.storage.personas import StoreDep

router = APIRouter(tags=["speech"])

SettingsDep = Annotated[Settings, Depends(get_settings)]

MEDIA_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/ogg"}


class TTSRequest(BaseModel):
    # TTS text with S2 cues (the `tts_text` from /chat/stream)
    text: str = Field(min_length=1)
    persona_id: str | None = None
    # Overrides the persona's voice; must be in the catalog (used for previews).
    voice_id: str | None = None


@router.get("/voices")
async def list_voices() -> list[VoiceOption]:
    return VOICES


@router.post("/tts")
async def tts(
    req: TTSRequest, client: TTSDep, store: StoreDep, settings: SettingsDep
) -> Response:
    if len(req.text) > settings.tts_max_chars:
        raise HTTPException(
            status_code=422, detail=f"text longer than {settings.tts_max_chars} chars"
        )
    if req.voice_id and req.voice_id not in VOICES_BY_ID:
        raise HTTPException(status_code=422, detail="Unknown voice")
    persona = store.get(req.persona_id) if req.persona_id else None
    voice_id = (
        req.voice_id
        or (persona.voice_id if persona else None)
        or settings.fish_default_voice_id
    )
    audio = await client.synthesize(validate_cues(req.text), voice_id=voice_id)
    return Response(content=audio, media_type=MEDIA_TYPES[settings.fish_tts_format])
