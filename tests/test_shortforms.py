import asyncio
import base64
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.ingest.models import Message
from app.llm.client import get_llm
from app.main import app
from app.persona.models import Persona, ShortForm
from app.persona.shortforms import (
    detect_shortforms,
    expand_shortforms,
    merge_shortforms,
)
from app.speech.tts import get_optional_tts
from app.storage.personas import PersonaStore, get_store
from tests.test_chat import FakeLLM, FakeTTS, events

SF = [
    ShortForm(short=s, full=f)
    for s, f in [("r", "are"), ("u", "you"), ("h", "hai"), ("kb", "kab")]
]


# ---------- expansion ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("r u coming?", "are you coming?"),
        ("U r late", "You are late"),  # capitalized short -> capitalized full
        ("kb aa rha h", "kab aa rha hai"),
        ("u're here, rush hour", "u're here, rush hour"),  # only whole words
        ("[laughing] r u ok", "[laughing] are you ok"),
        ("", ""),
    ],
)
def test_expand(text, expected):
    assert expand_shortforms(text, SF) == expected


def test_disabled_short_forms_are_kept():
    forms = [
        ShortForm(short="r", full="are", enabled=False),
        ShortForm(short="u", full="you"),
    ]
    assert expand_shortforms("r u", forms) == "r you"


# ---------- detection ----------


def chat(lines, sender="Kabir"):
    t = datetime(2024, 1, 1)
    out = []
    for i, line in enumerate(lines):
        out.append(Message(ts=t + timedelta(minutes=2 * i), sender="Neha", text="hmm"))
        out.append(
            Message(ts=t + timedelta(minutes=2 * i + 1), sender=sender, text=line)
        )
    return out


class ShortLLM:
    def __init__(self, items=None, fail=False):
        self.items = items or []
        self.fail = fail
        self.prompts = []

    async def generate(self, *, prompt, **kwargs):
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("model down")
        return json.dumps({"items": self.items})


LINES = ["kya scn h", "r u there", "scn kya h", "r u sure", "once only zzq"]


def run(coro):
    return asyncio.run(coro)


def test_detect_dictionary_plus_llm():
    llm = ShortLLM(
        [
            {"short": "scn", "full": "scene"},
            {"short": "kya", "full": "kya"},  # not a short form: same as itself
            {"short": "zzq", "full": "something"},  # used once: not a candidate
            {"short": "nope", "full": "x"},  # not in the chat
        ]
    )
    found = run(detect_shortforms(llm, Settings(), "Kabir", "Kabir", chat(LINES)))
    by = {f.short: f for f in found}
    assert {k: v.full for k, v in by.items()} == {
        "h": "hai",
        "r": "are",
        "u": "you",
        "scn": "scene",
    }
    assert by["scn"].count == 2 and by["scn"].example == "kya scn h"
    # Only the persona's own messages are scanned, and candidates exclude dictionary hits
    assert "hmm" not in llm.prompts[0] and "\nh (" not in llm.prompts[0]


def test_detect_survives_llm_failure_and_works_without_llm():
    msgs = chat(LINES)
    for llm in (ShortLLM(fail=True), None):
        found = run(detect_shortforms(llm, Settings(), "Kabir", "Kabir", msgs))
        assert {f.short for f in found} == {"h", "r", "u"}


def test_merge_keeps_user_edits():
    existing = [
        ShortForm(
            short="h", full="hain", enabled=False, count=2
        ),  # user edited + disabled
        ShortForm(short="gg", full="good game"),  # hand-added
    ]
    detected = [
        ShortForm(short="h", full="hai", count=5, example="kya h"),
        ShortForm(short="r", full="are", count=3),
    ]
    merged = {sf.short: sf for sf in merge_shortforms(existing, detected)}
    assert (merged["h"].full, merged["h"].enabled, merged["h"].count) == (
        "hain",
        False,
        5,
    )
    assert merged["r"].full == "are" and merged["gg"].full == "good game"


# ---------- speech vs display ----------


@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=str(tmp_path))
    yield TestClient(app), tmp_path
    app.dependency_overrides.clear()


def set_forms(client_and_path, **fields):
    c, _ = client_and_path
    body = {"shortforms": [sf.model_dump() for sf in SF], **fields}
    return c.put("/api/v1/personas/demo-rohan/shortforms", json=body)


def chat_stream(c, tts=None):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(
        ["r u aa rha h 😂\n", "kb milega"]
    )
    app.dependency_overrides[get_optional_tts] = lambda: tts
    body = {
        "persona_id": "demo-rohan",
        "turns": [{"role": "user", "text": "hi"}],
        "speak": tts is not None,
    }
    return events(c.post("/api/v1/chat/stream", json=body))


def test_speech_says_full_forms_but_text_keeps_style(client):
    assert set_forms(client).status_code == 200
    tts = FakeTTS()
    evs = chat_stream(client[0], tts)
    done = next(d for e, d in evs if e == "done")
    assert done["bubbles"] == [
        "r u aa rha h 😂",
        "kb milega",
    ]  # texting style kept on screen
    assert tts.calls == ["[joking] are you aa rha hai", "kab milega"]
    assert done["tts_text"] == "[joking] are you aa rha hai\nkab milega"
    assert all(
        base64.b64decode(d["audio"]) == b"ID3fake" for e, d in evs if e == "audio"
    )


def test_show_in_full_option_expands_text(client):
    set_forms(client, expand_shortforms_in_text=True)
    done = next(d for e, d in chat_stream(client[0]) if e == "done")
    assert done["bubbles"] == ["are you aa rha hai 😂", "kab milega"]


def test_speech_expansion_can_be_turned_off(client):
    set_forms(client, expand_shortforms_in_speech=False)
    tts = FakeTTS()
    chat_stream(client[0], tts)
    assert tts.calls == ["[joking] r u aa rha h", "kb milega"]


# ---------- API ----------


def test_update_validates_and_normalizes(client):
    c, _ = client
    r = c.put(
        "/api/v1/personas/demo-rohan/shortforms",
        json={"shortforms": [{"short": " TMRW ", "full": " tomorrow "}]},
    )
    assert r.status_code == 200
    assert r.json()["shortforms"][0] | {} == {
        "short": "tmrw",
        "full": "tomorrow",
        "count": 0,
        "example": "",
        "enabled": True,
    }
    dup = {"shortforms": [{"short": "r", "full": "are"}, {"short": "R", "full": "are"}]}
    assert c.put("/api/v1/personas/demo-rohan/shortforms", json=dup).status_code == 422
    spaced = {"shortforms": [{"short": "r u", "full": "are you"}]}
    assert (
        c.put("/api/v1/personas/demo-rohan/shortforms", json=spaced).status_code == 422
    )


def test_detect_needs_a_chat(client):
    c, _ = client
    app.dependency_overrides[get_llm] = lambda: ShortLLM()
    assert c.post("/api/v1/personas/demo-rohan/shortforms/detect").status_code == 400


def test_detect_from_stored_chat_keeps_edits(client):
    c, tmp = client
    store = PersonaStore(tmp)
    store.save(
        Persona(
            id="kabir-abc123",
            name="Kabir",
            sender_name="Kabir",
            shortforms=[ShortForm(short="h", full="hain")],  # user's own edit
        )
    )
    store.save_messages("kabir-abc123", chat(LINES))
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: ShortLLM(
        [{"short": "scn", "full": "scene"}]
    )
    r = c.post("/api/v1/personas/kabir-abc123/shortforms/detect")
    assert r.status_code == 200
    forms = {f["short"]: f["full"] for f in r.json()["shortforms"]}
    assert forms == {"h": "hain", "r": "are", "u": "you", "scn": "scene"}
    assert store.get("kabir-abc123").shortforms[0].short == "h"  # persisted
