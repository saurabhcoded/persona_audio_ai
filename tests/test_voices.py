import asyncio

import pytest
from fastapi.testclient import TestClient
from fishaudio.exceptions import RateLimitError

from app.core.config import Settings, get_settings
from app.llm.client import get_llm
from app.main import app
from app.speech.tts import TTSClient, get_tts
from app.speech.voices import VOICES
from tests.test_personas_api import FakeLLM, create

GIRL_HINDI = "4d7609058bd34213b1378b29efbde1f1"
BOY_HINDI = "528f686ef2154885b368dd4b93fb8728"


class FakeTTS:
    def __init__(self):
        self.voices = []

    async def synthesize(self, text, voice_id=None):
        self.voices.append(voice_id)
        return b"ID3fake"


@pytest.fixture
def env(tmp_path):
    settings = Settings(
        data_dir=str(tmp_path), persona_min_messages=5, embedding_dim=32
    )
    tts = FakeTTS()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_tts] = lambda: tts
    yield TestClient(app), tts
    app.dependency_overrides.clear()


def test_catalog_has_two_male_two_female_defaults_and_hindi_voices():
    english = [v for v in VOICES if v.language == "English"]
    assert sorted(v.gender for v in english) == ["female", "female", "male", "male"]
    by_id = {v.id: v.name for v in VOICES}
    assert by_id[GIRL_HINDI] == "Girl Hindi"
    assert by_id[BOY_HINDI] == "Boy Hindi"


def test_list_voices(env):
    client, _ = env
    assert [v["id"] for v in client.get("/api/v1/voices").json()] == [
        v.id for v in VOICES
    ]


def test_persona_voice_is_stored_and_used_for_speech(env):
    client, tts = env
    pid = create(client, voice_id=BOY_HINDI).json()["id"]
    assert client.get(f"/api/v1/personas/{pid}").json()["voice_id"] == BOY_HINDI
    r = client.post("/api/v1/tts", json={"persona_id": pid, "text": "[happy] haan"})
    assert r.status_code == 200
    assert tts.voices == [BOY_HINDI]


def test_unknown_voice_rejected_on_create(env):
    client, _ = env
    assert create(client, voice_id="not-a-voice").status_code == 422


def test_preview_without_persona_uses_given_voice(env):
    client, tts = env
    r = client.post(
        "/api/v1/tts", json={"voice_id": GIRL_HINDI, "text": "[happy] hello"}
    )
    assert r.status_code == 200
    assert tts.voices == [GIRL_HINDI]


def test_preview_rejects_unknown_voice(env):
    client, _ = env
    r = client.post("/api/v1/tts", json={"voice_id": "nope", "text": "hello"})
    assert r.status_code == 422


def test_tts_client_retries_rate_limit(monkeypatch):
    client = TTSClient("key", "s2.1-pro", "mp3")
    calls = []

    async def convert(**kwargs):
        calls.append(kwargs["reference_id"])
        if len(calls) < 2:
            raise RateLimitError(429, "Too many requests")
        return b"audio"

    async def no_sleep(_):
        return None

    monkeypatch.setattr(client._client.tts, "convert", convert)
    monkeypatch.setattr("app.speech.tts.asyncio.sleep", no_sleep)
    assert asyncio.run(client.synthesize("hi", GIRL_HINDI)) == b"audio"
    assert calls == [GIRL_HINDI, GIRL_HINDI]
