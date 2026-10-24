import asyncio
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from fishaudio import AsyncFishAudio
from fishaudio.exceptions import RateLimitError

from app.core.config import Settings, get_settings


class TTSClient:
    """Fish Audio text-to-speech. Text must already carry S2 cues (see app.speech.cues)."""

    def __init__(self, api_key: str, model: str, audio_format: str):
        self._client = AsyncFishAudio(api_key=api_key)
        self.model = model
        self.audio_format = audio_format

    async def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """Retries 429s: Fish limits concurrent requests per account (hit at 6 parallel)."""
        for attempt in range(3):
            try:
                # The SDK's Model type hint predates s2.1-pro; the API accepts it.
                return await self._client.tts.convert(
                    text=text,
                    reference_id=voice_id,
                    format=self.audio_format,
                    model=self.model,  # type: ignore[arg-type]
                )
            except RateLimitError:
                if attempt == 2:
                    raise
                await asyncio.sleep(1 + attempt)
        raise AssertionError("unreachable")


@lru_cache
def _client(api_key: str, model: str, audio_format: str) -> TTSClient:
    return TTSClient(api_key, model, audio_format)


def get_tts(settings: Annotated[Settings, Depends(get_settings)]) -> TTSClient:
    if not settings.fish_audio_api_key:
        raise HTTPException(
            status_code=503, detail="FISH_AUDIO_API_KEY is not configured"
        )
    return _client(
        settings.fish_audio_api_key, settings.fish_tts_model, settings.fish_tts_format
    )


TTSDep = Annotated[TTSClient, Depends(get_tts)]
