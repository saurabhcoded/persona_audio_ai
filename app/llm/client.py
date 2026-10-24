import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.core.config import Settings, get_settings


class ChatTurn(BaseModel):
    role: Literal["user", "persona"]
    text: str


class LLMClient:
    """Gemini on Vertex AI (auth via gcloud ADC). See agents/knowledge/vertex-gemini.md."""

    def __init__(self, project: str | None, location: str):
        self._client = genai.Client(vertexai=True, project=project, location=location)

    async def stream(
        self,
        *,
        model: str,
        system: str,
        turns: list[ChatTurn],
        temperature: float = 0.9,
        thinking: str | None = None,
        max_output_tokens: int = 400,
    ) -> AsyncIterator[str]:
        contents = [
            types.Content(
                role="user" if t.role == "user" else "model",
                parts=[types.Part.from_text(text=t.text)],
            )
            for t in turns
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=thinking)
            if thinking
            else None,
        )
        stream = await self._client.aio.models.generate_content_stream(
            model=model, contents=contents, config=config
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def generate(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        temperature: float = 0.4,
        json_schema: dict | None = None,
    ) -> str:
        """One-shot generation; with json_schema the reply is JSON matching it."""
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_schema else None,
            response_schema=json_schema,
        )
        resp = await _retry(
            lambda: self._client.aio.models.generate_content(
                model=model, contents=prompt, config=config
            )
        )
        return resp.text or ""

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        dim: int,
        concurrency: int = 16,
    ) -> list[list[float]]:
        """Embed texts one call each (gemini-embedding-2 merges multi-text requests
        into a single vector), `concurrency` calls at a time."""
        config = types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY", output_dimensionality=dim
        )
        sem = asyncio.Semaphore(concurrency)

        async def one(text: str) -> list[float]:
            async with sem:
                resp = await _retry(
                    lambda: self._client.aio.models.embed_content(
                        model=model, contents=text, config=config
                    )
                )
                return resp.embeddings[0].values

        return await asyncio.gather(*(one(t) for t in texts))


async def _retry(call, attempts: int = 4):
    """Retry rate-limit / transient server errors with exponential backoff."""
    for attempt in range(attempts):
        try:
            return await call()
        except genai_errors.APIError as e:
            if attempt == attempts - 1 or e.code not in (429, 500, 503):
                raise
            await asyncio.sleep(2**attempt)


@lru_cache
def _client(project: str | None, location: str) -> LLMClient:
    return LLMClient(project, location)


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> LLMClient:
    return _client(settings.gcp_project, settings.gcp_location)


LLMDep = Annotated[LLMClient, Depends(get_llm)]
