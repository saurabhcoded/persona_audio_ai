import asyncio
import base64

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.llm.client import get_llm
from app.main import app
from app.speech.tts import get_optional_tts
from tests.test_chat import FakeLLM, FakeTTS, events


@pytest.fixture
def client(tmp_path):
    # Isolated data dir: never read or write the developer's real personas.
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=str(tmp_path))
    yield TestClient(app)
    app.dependency_overrides.clear()


class SlowLLM(FakeLLM):
    """Pauses between chunks so speech of early lines can overtake the text stream."""

    async def stream(self, **kwargs):
        for chunk in self.chunks:
            yield chunk
            await asyncio.sleep(0.05)


class FailingTTS(FakeTTS):
    async def synthesize(self, text, voice_id=None):
        self.calls.append(text)
        if len(self.calls) == 1:
            raise RuntimeError("fish down")
        return b"ID3fake"


def speak_body(speak=True):
    return {
        "persona_id": "demo-rohan",
        "turns": [{"role": "user", "text": "kal match?"}],
        "speak": speak,
    }


def run(client, llm, tts, speak=True):
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_optional_tts] = lambda: tts
    return client.post("/api/v1/chat/stream", json=speak_body(speak))


def test_each_line_is_spoken_in_order(client):
    tts = FakeTTS()
    r = run(client, FakeLLM(["Rohan: haan ", "pakka 😂\nRo", "han: chal 🫂"]), tts)
    evs = events(r)
    audio = [d for e, d in evs if e == "audio"]
    assert [a["index"] for a in audio] == [0, 1]
    assert all(base64.b64decode(a["audio"]) == b"ID3fake" for a in audio)
    assert audio[0]["format"] == "mp3"
    # Same guard + emoji->cue conversion as the final tts_text, line by line
    assert tts.calls == ["[joking] haan pakka", "[soft tone][empathetic] chal"]
    done = next(d for e, d in evs if e == "done")
    assert done["tts_text"] == "\n".join(tts.calls)


def test_first_line_audio_arrives_before_text_finishes(client):
    r = run(
        client,
        SlowLLM(["haan pakka\n", "tu ", "bas ", "late ", "mat ", "hona"]),
        FakeTTS(),
    )
    names = [e for e, _ in events(r)]
    last_delta = max(i for i, name in enumerate(names) if name == "delta")
    assert names.index("audio") < last_delta


def test_failed_line_reports_audio_error_and_keeps_going(client):
    tts = FailingTTS()
    evs = events(run(client, FakeLLM(["one\n", "two"]), tts))
    spoken = [(e, d["index"]) for e, d in evs if e in ("audio", "audio_error")]
    assert spoken == [("audio_error", 0), ("audio", 1)]
    assert any(e == "done" for e, _ in evs)


def test_pii_is_never_spoken(client):
    tts = FakeTTS()
    run(client, FakeLLM(["mera number 9876543210 hai"]), tts)
    assert tts.calls == ["mera number hai"]


def test_no_speech_unless_requested(client):
    tts = FakeTTS()
    evs = events(run(client, FakeLLM(["haan 😂"]), tts, speak=False))
    assert tts.calls == []
    assert not any(e.startswith("audio") for e, _ in evs)


def test_speak_without_fish_key_is_503(client):
    r = run(client, FakeLLM(["haan"]), None)
    assert r.status_code == 503
