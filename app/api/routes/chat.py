from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.chat.service import stream_reply
from app.core.config import Settings, get_settings
from app.llm.client import ChatTurn, LLMDep
from app.location.assistant import LocationDep, PendingRide
from app.speech.tts import OptionalTTSDep
from app.storage.personas import StoreDep

router = APIRouter(tags=["chat"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class ChatRequest(BaseModel):
    persona_id: str
    turns: list[ChatTurn] = Field(min_length=1)
    # Speak each line while the reply streams (audio events in the same SSE stream)
    speak: bool = False
    # Draft ride from the last `ride_preview` event, until confirmed or replaced
    pending_ride: PendingRide | None = None

    @field_validator("turns")
    @classmethod
    def last_turn_is_user(cls, turns: list[ChatTurn]) -> list[ChatTurn]:
        if turns[-1].role != "user":
            raise ValueError("last turn must be from the user")
        return turns


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    llm: LLMDep,
    store: StoreDep,
    settings: SettingsDep,
    tts: OptionalTTSDep,
    location: LocationDep,
) -> StreamingResponse:
    """Streams the persona's reply as server-sent events (see app.chat.service.stream_reply).
    With `speak`, audio for each line is streamed too (needs FISH_AUDIO_API_KEY). With
    location assist on, the persona can plan rides and save places (ride cards in the stream)."""
    persona = store.get(req.persona_id)
    if persona.status != "ready":
        raise HTTPException(status_code=409, detail=f"Persona is {persona.status}")
    if req.speak and tts is None:
        raise HTTPException(
            status_code=503, detail="FISH_AUDIO_API_KEY is not configured"
        )
    return StreamingResponse(
        stream_reply(
            persona,
            req.turns,
            llm,
            store,
            settings,
            tts if req.speak else None,
            location,
            req.pending_ride,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
