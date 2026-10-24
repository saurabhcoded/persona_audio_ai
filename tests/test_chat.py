import json

import pytest
from fastapi.testclient import TestClient

from app.chat.service import PrefixStripper
from app.core.config import Settings, get_settings
from app.llm.client import get_llm
from app.main import app
from app.speech.tts import get_tts


class FakeLLM:
    def __init__(self, chunks: list[str], fail: bool = False):
        self.chunks = chunks
        self.fail = fail

    async def stream(self, **kwargs):
        for chunk in self.chunks:
            yield chunk
        if self.fail:
            raise RuntimeError("boom")


class FakeTTS:
    def __init__(self):
        self.calls = []

    async def synthesize(self, text, voice_id=None):
        self.calls.append(text)
        return b"ID3fake"


@pytest.fixture
def client(tmp_path):
    # Isolated data dir: never read or write the developer's real personas.
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=str(tmp_path))
    yield TestClient(app)
    app.dependency_overrides.clear()


def events(response) -> list[tuple[str, dict]]:
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def body(text="bhai kal match?"):
    return {"persona_id": "demo-rohan", "turns": [{"role": "user", "text": text}]}


def test_prefix_stripper_handles_split_chunks():
    s = PrefixStripper("Rohan")
    out = (
        "".join(
            s.feed(c) for c in ["Roh", "an: haan ", "pakka\n  Ro", "han:chal\nRo", "ti"]
        )
        + s.flush()
    )
    assert out == "haan pakka\nchal\nRoti"


def test_stream_emits_deltas_then_done(client):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(
        ["Rohan: haan ", "pakka 😂\n", "Rohan: chal"]
    )
    r = client.post("/api/v1/chat/stream", json=body())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = events(r)
    assert [e for e, _ in evs[:-1]] == ["delta"] * (len(evs) - 1)
    assert "".join(d["text"] for _, d in evs[:-1]) == "haan pakka 😂\nchal"
    name, done = evs[-1]
    assert name == "done"
    assert done["bubbles"] == ["haan pakka 😂", "chal"]
    assert done["tts_text"] == "[joking] haan pakka\nchal"


def test_stream_reports_error_event(client):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(["haan"], fail=True)
    evs = events(client.post("/api/v1/chat/stream", json=body()))
    assert evs[-1][0] == "error"


def test_unknown_persona_is_404(client):
    app.dependency_overrides[get_llm] = lambda: FakeLLM([])
    r = client.post("/api/v1/chat/stream", json={**body(), "persona_id": "nope"})
    assert r.status_code == 404


def test_last_turn_must_be_user(client):
    app.dependency_overrides[get_llm] = lambda: FakeLLM([])
    r = client.post(
        "/api/v1/chat/stream",
        json={"persona_id": "demo-rohan", "turns": [{"role": "persona", "text": "hi"}]},
    )
    assert r.status_code == 422


def test_personas_lists_demo(client):
    assert [p["id"] for p in client.get("/api/v1/personas").json()] == ["demo-rohan"]


def test_tts_returns_audio(client):
    fake = FakeTTS()
    app.dependency_overrides[get_tts] = lambda: fake
    r = client.post(
        "/api/v1/tts", json={"persona_id": "demo-rohan", "text": "(happy) haan"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert fake.calls == ["[happy] haan"]


def test_tts_rejects_long_text(client):
    app.dependency_overrides[get_tts] = lambda: FakeTTS()
    r = client.post(
        "/api/v1/tts", json={"persona_id": "demo-rohan", "text": "a" * 5000}
    )
    assert r.status_code == 422


class EmptyThenReplyLLM:
    def __init__(self):
        self.calls = 0

    async def stream(self, **kwargs):
        self.calls += 1
        if self.calls > 1:
            yield "haan"


def test_empty_model_reply_is_retried_once(client):
    llm = EmptyThenReplyLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    evs = events(client.post("/api/v1/chat/stream", json=body()))
    assert llm.calls == 2
    assert evs[-1] == ("done", {"bubbles": ["haan"], "tts_text": "haan"})
