from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.speech.cues import validate_cues
from app.speech.tts import TTSDep
from app.speech.voices import VOICE_ID, VoiceLibraryDep, VoiceOption, voice_from_fish
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


class AddVoiceRequest(BaseModel):
    voice_id: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=60)  # defaults to the Fish title


@router.get("/voices")
async def list_voices(library: VoiceLibraryDep) -> list[VoiceOption]:
    """Built-in voices, then the user's custom ones."""
    return library.all()


@router.post("/voices", status_code=201)
async def add_voice(
    req: AddVoiceRequest, client: TTSDep, library: VoiceLibraryDep
) -> VoiceOption:
    """Add a Fish Audio voice by ID (the 32-character id in the voice's fish.audio URL)."""
    voice_id = req.voice_id.strip().lower()
    if not VOICE_ID.match(voice_id):
        raise HTTPException(
            status_code=422,
            detail="A Fish voice ID is 32 letters/digits (from its fish.audio URL)",
        )
    existing = library.get(voice_id)
    if existing and not existing.custom:
        raise HTTPException(
            status_code=409, detail=f"Already built in as {existing.name}"
        )
    fish_voice = await client.get_voice(voice_id)
    if fish_voice is None:
        raise HTTPException(
            status_code=422, detail="Fish Audio has no voice with that ID"
        )
    return library.add(voice_from_fish(fish_voice, req.name))


@router.delete("/voices/{voice_id}", status_code=204)
async def remove_voice(voice_id: str, library: VoiceLibraryDep) -> Response:
    voice = library.get(voice_id)
    if voice is None:
        raise HTTPException(status_code=404, detail="Unknown voice")
    if not voice.custom:
        raise HTTPException(status_code=400, detail="Built-in voices can't be removed")
    library.remove(voice_id)
    return Response(status_code=204)


@router.post("/tts")
async def tts(
    req: TTSRequest,
    client: TTSDep,
    store: StoreDep,
    library: VoiceLibraryDep,
    settings: SettingsDep,
) -> Response:
    if len(req.text) > settings.tts_max_chars:
        raise HTTPException(
            status_code=422, detail=f"text longer than {settings.tts_max_chars} chars"
        )
    if req.voice_id and library.get(req.voice_id) is None:
        raise HTTPException(status_code=422, detail="Unknown voice")
    persona = store.get(req.persona_id) if req.persona_id else None
    voice_id = (
        req.voice_id
        or (persona.voice_id if persona else None)
        or settings.fish_default_voice_id
    )
    audio = await client.synthesize(validate_cues(req.text), voice_id=voice_id)
    return Response(content=audio, media_type=MEDIA_TYPES[settings.fish_tts_format])
