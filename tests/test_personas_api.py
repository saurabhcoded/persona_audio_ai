import hashlib
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.llm.client import get_llm
from app.main import app

NNBSP = " "
PHONE = "9876543210"
EMAIL = "aman.v@example.com"

# (Neha says, Aman replies) — synthetic conversation
EXCHANGES = [
    ("kal match chalein?", "haan pakka 😂\ntu late mat hona"),
    (f"mera number {PHONE} save kar le", "done 😂"),
    ("mood off hai yaar", "kya hua 🫂\nchai pe aaja"),
    ("boss ne weekend pe kaam diya", "classic 😂"),
    ("mail bhej diya?", f"haan {EMAIL} pe bheja 😂"),
    ("gym chalein kal?", "subah 6 baje? mushkil hai 😅"),
]


def chat_export(rounds: int = 4) -> str:
    t = datetime(2024, 3, 12, 20, 0)
    lines = [f"12/03/24, 8:00{NNBSP}pm - Messages and calls are end-to-end encrypted."]
    for _ in range(rounds):
        for theirs, reply in EXCHANGES:
            for sender, text in [("Neha", theirs), ("Aman Verma", reply)]:
                t += timedelta(minutes=10)
                stamp = (
                    t.strftime("%d/%m/%y, %-I:%M") + NNBSP + t.strftime("%p").lower()
                )
                lines.append(f"{stamp} - {sender}: {text}")
        t += timedelta(minutes=2)
        lines.append(
            t.strftime("%d/%m/%y, %-I:%M") + NNBSP + "pm - Aman Verma: <Media omitted>"
        )
    return "\n".join(lines) + "\n"


def _vec(text: str, dim: int = 32) -> list[float]:
    """Deterministic bag-of-words vector so retrieval is meaningful in tests."""
    v = [0.0] * dim
    for word in text.lower().split():
        v[int(hashlib.md5(word.encode()).hexdigest(), 16) % dim] += 1
    return v


class FakeLLM:
    def __init__(self):
        self.systems: list[str] = []
        self.prompts: list[str] = []

    async def stream(self, *, system, **kwargs):
        self.systems.append(system)
        yield "haan 😂"

    async def generate(self, *, prompt, json_schema=None, **kwargs):
        self.prompts.append(prompt)
        if json_schema:
            return json.dumps(
                {
                    "items": [
                        {
                            "emoji": "😂",
                            "meaning": "laugh",
                            "cue": "[chuckling]",
                            "spoken_as": "heh",
                        },
                        {
                            "emoji": "🫂",
                            "meaning": "care",
                            "cue": "[soft tone",
                            "spoken_as": "",
                        },
                    ]
                }
            )
        return "- texts in lowercase hinglish\n- Never says: formal english"

    async def embed(self, texts, **kwargs):
        return [_vec(t) for t in texts]


@pytest.fixture
def env(tmp_path):
    settings = Settings(
        data_dir=str(tmp_path), persona_min_messages=5, embedding_dim=32
    )
    llm = FakeLLM()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_llm] = lambda: llm
    yield TestClient(app), llm, tmp_path
    app.dependency_overrides.clear()


def upload(content: str):
    return {"file": ("chat.txt", content.encode(), "text/plain")}


def create(client, **form):
    data = {"name": "Aman", "sender": "Aman Verma", "consent": "true", **form}
    return client.post("/api/v1/personas", data=data, files=upload(chat_export()))


def test_participants_lists_senders_and_stores_nothing(env):
    client, _, tmp = env
    r = client.post("/api/v1/personas/participants", files=upload(chat_export()))
    assert r.status_code == 200
    body = r.json()
    assert {p["name"] for p in body["participants"]} == {"Neha", "Aman Verma"}
    assert not any(tmp.iterdir())


def test_participants_rejects_non_chat(env):
    client, _, _ = env
    r = client.post("/api/v1/personas/participants", files=upload("just some text"))
    assert r.status_code == 422


def test_create_build_chat_delete(env):
    client, llm, tmp = env
    r = create(client)
    assert r.status_code == 202
    pid = r.json()["id"]

    # TestClient runs background tasks before returning, so the build is done.
    detail = client.get(f"/api/v1/personas/{pid}").json()
    assert detail["status"] == "ready", detail
    assert detail["card"].startswith("- texts in lowercase")
    assert detail["emoji_map"] == {
        "😂": {"cue": "[chuckling]", "spoken_as": "heh"}
    }  # invalid cue dropped
    assert detail["report"]["pii"] == {"PHONE": 4, "EMAIL": 4}
    assert detail["stats"]["top_emojis"][0] == "😂"
    assert pid in [p["id"] for p in client.get("/api/v1/personas").json()]

    # Privacy regression: no raw PII anywhere on disk, and LLM prompts saw only redacted text.
    for path in tmp.rglob("*"):
        if path.is_file() and path.suffix != ".npy":
            content = path.read_text()
            assert PHONE not in content and EMAIL not in content, path.name
    assert all(PHONE not in p and EMAIL not in p for p in llm.prompts)

    # Chat retrieves the persona's real reply to a similar message.
    r = client.post(
        "/api/v1/chat/stream",
        json={
            "persona_id": pid,
            "turns": [{"role": "user", "text": "kal match chalein?"}],
        },
    )
    assert "Aman: haan pakka 😂" in llm.systems[-1]
    done = json.loads(r.text.strip().split("\n\n")[-1].split("data: ", 1)[1])
    assert done["tts_text"] == "[chuckling] heh haan"  # persona's own emoji map

    assert client.delete(f"/api/v1/personas/{pid}").status_code == 204
    assert client.get(f"/api/v1/personas/{pid}").status_code == 404
    assert not any((tmp / "personas").iterdir())


def test_consent_required(env):
    client, _, tmp = env
    assert create(client, consent="false").status_code == 422
    assert not (tmp / "personas").exists()


def test_unknown_sender_rejected(env):
    client, _, _ = env
    assert create(client, sender="Someone Else").status_code == 422


def test_demo_persona_cannot_be_deleted(env):
    client, _, _ = env
    assert client.delete("/api/v1/personas/demo-rohan").status_code == 400


def test_bad_persona_id_is_404(env):
    client, _, _ = env
    assert client.get("/api/v1/personas/..%2F..%2Fetc").status_code == 404
