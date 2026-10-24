import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.ingest.models import Message
from app.llm.client import get_llm
from app.main import app
from app.persona.builder import build_persona
from app.persona.models import Persona
from app.speech.tts import get_tts
from app.speech.voices import VOICES
from app.storage.personas import PersonaStore
from tests.test_personas_api import FakeLLM, create

CUSTOM = "aaaabbbbccccddddeeeeffff00001111"
GIRL_HINDI = "4d7609058bd34213b1378b29efbde1f1"


class FakeTTS:
    def __init__(self):
        self.voices = []

    async def get_voice(self, voice_id):
        if voice_id != CUSTOM:
            return None
        return SimpleNamespace(
            id=CUSTOM,
            title="Nani ji",
            tags=["female", "old", "warm", "storytelling"],
            languages=["hi", "en"],
        )

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
    yield TestClient(app), tts, tmp_path
    app.dependency_overrides.clear()


def add(client, voice_id=CUSTOM, name=None):
    return client.post("/api/v1/voices", json={"voice_id": voice_id, "name": name})


# ---------- custom voices ----------


def test_add_voice_by_id_fills_details_from_fish(env):
    client, _, tmp = env
    r = add(client, f"  {CUSTOM.upper()} ")  # pasted with spaces / caps
    assert r.status_code == 201
    v = r.json()
    assert (v["id"], v["name"], v["gender"], v["language"]) == (
        CUSTOM,
        "Nani ji",
        "female",
        "Hindi, English",
    )
    assert v["description"] == "old, warm, storytelling" and v["custom"] is True
    ids = [x["id"] for x in client.get("/api/v1/voices").json()]
    assert ids == [x.id for x in VOICES] + [CUSTOM]  # built-ins first
    assert (tmp / "voices.json").is_file()


def test_custom_name_overrides_fish_title(env):
    client, _, _ = env
    assert add(client, name="Dadi").json()["name"] == "Dadi"


@pytest.mark.parametrize(
    ("voice_id", "status"),
    [("not-a-voice", 422), ("0" * 32, 422), (GIRL_HINDI, 409)],
)
def test_add_voice_rejections(env, voice_id, status):
    client, _, _ = env
    assert add(client, voice_id).status_code == status


def test_remove_custom_voice_only(env):
    client, _, _ = env
    add(client)
    assert client.delete(f"/api/v1/voices/{CUSTOM}").status_code == 204
    assert CUSTOM not in [x["id"] for x in client.get("/api/v1/voices").json()]
    assert client.delete(f"/api/v1/voices/{CUSTOM}").status_code == 404
    assert client.delete(f"/api/v1/voices/{GIRL_HINDI}").status_code == 400


def test_custom_voice_usable_for_new_persona_and_preview(env):
    client, tts, _ = env
    add(client)
    assert create(client, voice_id=CUSTOM).status_code == 202
    assert (
        client.post(
            "/api/v1/tts", json={"voice_id": CUSTOM, "text": "hello"}
        ).status_code
        == 200
    )
    assert tts.voices == [CUSTOM]


# ---------- changing a persona's voice ----------


def test_change_demo_persona_voice(env):
    client, tts, _ = env
    r = client.patch("/api/v1/personas/demo-rohan/voice", json={"voice_id": GIRL_HINDI})
    assert r.status_code == 200 and r.json()["voice_id"] == GIRL_HINDI
    assert client.get("/api/v1/personas/demo-rohan").json()["voice_id"] == GIRL_HINDI
    client.post("/api/v1/tts", json={"persona_id": "demo-rohan", "text": "haan"})
    assert tts.voices == [GIRL_HINDI]
    # back to the default voice
    client.patch("/api/v1/personas/demo-rohan/voice", json={"voice_id": None})
    assert client.get("/api/v1/personas/demo-rohan").json()["voice_id"] is None


def test_change_chat_persona_voice_to_custom(env):
    client, _, _ = env
    add(client)
    pid = create(client, voice_id=GIRL_HINDI).json()["id"]
    r = client.patch(f"/api/v1/personas/{pid}/voice", json={"voice_id": CUSTOM})
    assert r.json()["voice_id"] == CUSTOM
    assert client.get(f"/api/v1/personas/{pid}").json()["voice_id"] == CUSTOM


def test_change_to_unknown_voice_rejected(env):
    client, _, _ = env
    r = client.patch("/api/v1/personas/demo-rohan/voice", json={"voice_id": "f" * 32})
    assert r.status_code == 422
    assert (
        client.patch(
            "/api/v1/personas/nope-123/voice", json={"voice_id": None}
        ).status_code
        == 404
    )


# ---------- build keeps a voice changed mid-build ----------


def messages():
    t = datetime(2024, 1, 1, 10, 0)
    out = []
    for i in range(10):
        out.append(
            Message(ts=t.replace(minute=i * 2), sender="Neha", text="kal milte hai?")
        )
        out.append(
            Message(ts=t.replace(minute=i * 2 + 1), sender="Aman", text="haan pakka 😂")
        )
    return out


def building_persona(store):
    p = Persona(
        id="aman-abc123",
        name="Aman",
        status="building",
        sender_name="Aman",
        voice_id=GIRL_HINDI,
    )
    store.save(p)
    return p


def test_build_keeps_voice_changed_during_build(tmp_path):
    store = PersonaStore(Path(tmp_path))
    p = building_persona(store)
    store.set_voice(p.id, CUSTOM)  # user switches voice while it builds
    settings = Settings(data_dir=str(tmp_path), embedding_dim=32)
    asyncio.run(build_persona(p, messages(), store, FakeLLM(), settings))
    built = store.get(p.id)
    assert built.status == "ready" and built.voice_id == CUSTOM


def test_build_does_not_resurrect_deleted_persona(tmp_path):
    store = PersonaStore(Path(tmp_path))
    p = building_persona(store)
    settings = Settings(data_dir=str(tmp_path), embedding_dim=32)

    class DeletingLLM(FakeLLM):
        async def generate(self, **kwargs):
            store.delete(p.id)  # user deletes it mid-build
            return await super().generate(**kwargs)

    asyncio.run(build_persona(p, messages(), store, DeletingLLM(), settings))
    assert not (Path(tmp_path) / "personas" / p.id).exists()
