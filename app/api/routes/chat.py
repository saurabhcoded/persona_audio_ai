from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.chat.service import stream_reply
from app.core.config import Settings, get_settings
from app.llm.client import ChatTurn, LLMDep
from app.storage.personas import StoreDep

router = APIRouter(tags=["chat"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class ChatRequest(BaseModel):
    persona_id: str
    turns: list[ChatTurn] = Field(min_length=1)

    @field_validator("turns")
    @classmethod
    def last_turn_is_user(cls, turns: list[ChatTurn]) -> list[ChatTurn]:
        if turns[-1].role != "user":
            raise ValueError("last turn must be from the user")
        return turns


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest, llm: LLMDep, store: StoreDep, settings: SettingsDep
) -> StreamingResponse:
    """Streams the persona's reply as server-sent events (see app.chat.service.stream_reply)."""
    persona = store.get(req.persona_id)
    if persona.status != "ready":
        raise HTTPException(status_code=409, detail=f"Persona is {persona.status}")
    return StreamingResponse(
        stream_reply(persona, req.turns, llm, store, settings),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
