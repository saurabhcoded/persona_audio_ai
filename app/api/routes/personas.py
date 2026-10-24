from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.guardrails.pipeline import sanitize_chat
from app.ingest.models import Message
from app.ingest.whatsapp import ExportError, parse_whatsapp, participants, read_export
from app.llm.client import LLMDep
from app.persona.builder import build_persona
from app.persona.models import Persona
from app.speech.cues import EmojiCue
from app.speech.voices import VOICES_BY_ID
from app.storage.personas import StoreDep

router = APIRouter(tags=["personas"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class PersonaSummary(BaseModel):
    id: str
    name: str
    tagline: str
    source: Literal["demo", "chat"]
    status: Literal["building", "ready", "failed"]
    error: str | None = None
    voice_id: str | None = None


class PersonaDetail(PersonaSummary):
    card: str
    style: str
    stats: dict | None
    report: dict | None
    emoji_map: dict[str, EmojiCue]
    created_at: datetime | None


class Participant(BaseModel):
    name: str
    messages: int


class ParticipantsResponse(BaseModel):
    participants: list[Participant]
    total_messages: int


def _summary(p: Persona) -> PersonaSummary:
    return PersonaSummary.model_validate(p.model_dump())


async def _read_messages(file: UploadFile, settings: Settings) -> list[Message]:
    """Parse the upload in memory. The raw export is never written to disk (FR-ING-04)."""
    limit = settings.upload_max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413, detail=f"File is larger than {settings.upload_max_mb} MB"
        )
    try:
        return parse_whatsapp(read_export(data, file.filename or ""))
    except ExportError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/personas")
async def list_personas(store: StoreDep) -> list[PersonaSummary]:
    return [_summary(p) for p in store.all()]


@router.get("/personas/{persona_id}")
async def get_persona_detail(persona_id: str, store: StoreDep) -> PersonaDetail:
    return PersonaDetail.model_validate(store.get(persona_id).model_dump())


@router.post("/personas/participants")
async def chat_participants(
    settings: SettingsDep, file: Annotated[UploadFile, File()]
) -> ParticipantsResponse:
    """Who is in this export, so the user can pick the persona. Nothing is stored."""
    messages = await _read_messages(file, settings)
    counts = participants(messages)
    return ParticipantsResponse(
        participants=[Participant(name=n, messages=c) for n, c in counts.most_common()],
        total_messages=len(messages),
    )


@router.post("/personas", status_code=202)
async def create_persona(
    background: BackgroundTasks,
    store: StoreDep,
    llm: LLMDep,
    settings: SettingsDep,
    name: Annotated[str, Form(min_length=1, max_length=60)],
    sender: Annotated[str, Form(min_length=1)],
    consent: Annotated[bool, Form()],
    file: Annotated[UploadFile, File()],
    voice_id: Annotated[str | None, Form()] = None,
    consent_basis: Annotated[str, Form()] = "persona consented",
) -> PersonaSummary:
    """Sanitize the export, store the persona as `building`, and build it in the background."""
    if not consent:
        raise HTTPException(
            status_code=422, detail="Consent is required to create a persona"
        )
    if voice_id and voice_id not in VOICES_BY_ID:
        raise HTTPException(status_code=422, detail="Unknown voice")
    messages = await _read_messages(file, settings)
    counts = participants(messages)
    if sender not in counts:
        raise HTTPException(
            status_code=422, detail="That participant isn't in this chat"
        )
    if counts[sender] < settings.persona_min_messages:
        raise HTTPException(
            status_code=422,
            detail=f"{sender} has only {counts[sender]} messages; "
            f"at least {settings.persona_min_messages} are needed",
        )

    clean, report = sanitize_chat(messages, sender)
    del messages  # raw text goes no further
    persona = Persona(
        id=store.new_id(name),
        name=name.strip(),
        tagline="Building persona…",
        status="building",
        created_at=datetime.now(),
        consent_basis=consent_basis,
        sender_name=sender,
        report=report.model_dump(),
        voice_id=voice_id or None,
    )
    store.save(persona)
    background.add_task(build_persona, persona, clean, store, llm, settings)
    return _summary(persona)


@router.delete("/personas/{persona_id}", status_code=204)
async def delete_persona(persona_id: str, store: StoreDep) -> Response:
    store.delete(persona_id)
    return Response(status_code=204)
