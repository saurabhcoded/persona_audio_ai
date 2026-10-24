import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from app.llm import client as client_module
from app.llm.client import LLMClient


def make_client(responses):
    """LLMClient whose genai stream returns/raises the given items in order."""
    llm = LLMClient.__new__(LLMClient)
    calls = []

    async def generate_content_stream(**kwargs):
        calls.append(kwargs)
        item = responses.pop(0)

        async def gen():
            if isinstance(item, Exception):
                raise item  # genai sends the request when iteration starts
            for text in item:
                yield SimpleNamespace(text=text)

        return gen()

    llm._client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content_stream=generate_content_stream)
        )
    )
    return llm, calls


async def collect(llm):
    return [c async for c in llm.stream(model="m", system="s", turns=[])]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", instant)


def rate_limited():
    return genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": "Resource exhausted",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )


def test_rate_limit_before_first_chunk_is_retried():
    llm, calls = make_client([rate_limited(), ["haan ", "bhai"]])
    assert asyncio.run(collect(llm)) == ["haan ", "bhai"]
    assert len(calls) == 2


def test_other_client_errors_are_not_retried():
    bad = genai_errors.ClientError(
        400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}
    )
    llm, calls = make_client([bad, ["never"]])
    with pytest.raises(genai_errors.ClientError):
        asyncio.run(collect(llm))
    assert len(calls) == 1
