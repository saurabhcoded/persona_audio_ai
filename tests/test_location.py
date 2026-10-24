import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.core.config import Settings, get_settings
from app.llm.client import get_llm
from app.location.assistant import LocationAssistant, get_location, is_confirmation
from app.location.maps import MapsError, Place, Route
from app.location.saved import SavedPlaces
from app.main import app

CITIES = ["New Delhi", "Noida", "Gurugram", "Faridabad"]


def place(pid, name, address, locality, types=("political",), lat=28.5, lng=77.3):
    return Place(
        id=pid,
        name=name,
        address=address,
        lat=lat,
        lng=lng,
        locality=locality,
        types=list(types),
    )


ND = place(
    "nd",
    "New Delhi",
    "New Delhi, Delhi",
    "New Delhi",
    ("locality", "political"),
    28.61,
    77.21,
)
FBD = place(
    "fbd",
    "Faridabad",
    "Faridabad, Haryana",
    "Faridabad",
    ("locality", "political"),
    28.41,
    77.31,
)
CP = place(
    "cp",
    "Connaught Place",
    "Connaught Place, New Delhi 110001",
    "New Delhi",
    ("sublocality", "political"),
)
HOME = place(
    "home1",
    "Sector 21C",
    "Sector 21C, Faridabad, Haryana 121001",
    "Faridabad",
    ("sublocality",),
)
S15_NOIDA = place(
    "s15n", "Sector 15", "Sector 15, Noida, UP", "Noida", ("sublocality", "political")
)
S15_FBD = place(
    "s15f",
    "Sector 15",
    "Sector 15, Faridabad, Haryana",
    "Faridabad",
    ("sublocality", "political"),
)
S15_SHOP = place(
    "shop",
    "Sector 15 Sweets",
    "Sector 15, Gurugram, Haryana",
    "Gurugram",
    ("restaurant",),
)


class FakeMaps:
    def __init__(self, fail=False):
        self.fail = fail
        self.results = {
            "new delhi": [ND],
            "faridabad": [FBD],
            "connaught place": [CP],
            "sector 21c, faridabad": [HOME],
            "sector 15": [S15_NOIDA],
            "sector 15, noida": [S15_NOIDA],
            "sector 15, faridabad": [S15_FBD],
            "sector 15, gurugram": [S15_SHOP],  # a shop, not an area: not an option
        }
        self.by_id = {p.id: p for ps in self.results.values() for p in ps}

    async def search(self, query, max_results=5):
        if self.fail:
            raise MapsError("down")
        return self.results.get(query.lower(), [])[:max_results]

    async def get(self, place_id):
        return self.by_id[place_id]

    async def route(self, origin, destination):
        return Route(distance_km=33.9, duration_min=47, typical_min=40)


@pytest.fixture
def assistant(tmp_path):
    return LocationAssistant(FakeMaps(), SavedPlaces(tmp_path / "places.json"), CITIES)


def run(coro):
    return asyncio.run(coro)


def save_home(assistant):
    run(
        assistant.execute(
            "save_place", {"label": "my home", "place": "Sector 21C, Faridabad"}
        )
    )


# ---------- resolution ----------


def test_resolves_specific_place(assistant):
    r = run(assistant.resolve("Connaught Place"))
    assert r.status == "ok" and r.place.id == "cp"


def test_city_alone_is_too_broad(assistant):
    r = run(assistant.resolve("New Delhi"))
    assert r.status == "too_broad"
    assert r.for_model() == {
        "status": "too_broad",
        "query": "New Delhi",
        "ask_for": "a specific area, sector, landmark or address in New Delhi",
    }


def test_unsaved_home_asks_for_it(assistant):
    for text in ("home", "my home", "ghar", "mera ghar"):
        r = run(assistant.resolve(text))
        assert (r.status, r.label) == ("unknown_saved_place", "home"), text


def test_generic_area_without_city_is_ambiguous(assistant):
    r = run(assistant.resolve("Sector 15"))
    assert r.status == "ambiguous"
    assert r.for_model()["options"] == ["Sector 15, Noida", "Sector 15, Faridabad"]


def test_area_with_city_is_not_ambiguous(assistant):
    r = run(assistant.resolve("Sector 15, Faridabad"))
    assert r.status == "ok" and r.place.id == "s15f"


def test_place_id_from_options(assistant):
    assert run(assistant.resolve("place_id:s15f")).place.id == "s15f"


# ---------- plan_ride: follow-ups, draft, confirm ----------


def test_city_to_city_asks_for_exact_spots(assistant):
    out = run(
        assistant.execute(
            "plan_ride", {"origin": "New Delhi", "destination": "Faridabad"}
        )
    )
    assert out.result["status"] == "need_info"
    assert out.result["origin"]["status"] == "too_broad"
    assert out.result["destination"]["status"] == "too_broad"
    assert out.events == []


def test_everything_unclear_is_reported_together(assistant):
    out = run(
        assistant.execute("plan_ride", {"origin": "home", "destination": "Sector 15"})
    )
    assert out.result["status"] == "need_info"
    assert out.result["origin"] == {"status": "unknown_saved_place", "label": "home"}
    assert out.result["destination"]["status"] == "ambiguous"
    assert out.events == [
        ("choices", {"options": ["Sector 15, Noida", "Sector 15, Faridabad"]})
    ]


def test_first_plan_is_a_draft_without_booking_link(assistant):
    save_home(assistant)
    out = run(
        assistant.execute(
            "plan_ride", {"origin": "ghar", "destination": "Connaught Place"}
        )
    )
    assert out.result["status"] == "needs_confirmation"
    assert (out.result["from"], out.result["to"]) == (
        "home",
        "Connaught Place, New Delhi",
    )
    assert "121001" not in json.dumps(
        out.result
    )  # saved address never goes to the model
    ((preview_name, card),) = out.events  # no choices: the UI shows a Confirm bar
    assert preview_name == "ride_preview" and card["preview"] is True
    assert "uber_url" not in card and "maps_url" not in card
    assert card["origin"] == {
        "label": "home",
        "name": "Sector 21C",
        "address": HOME.address,
    }
    assert card["draft"] == {
        "origin_ref": "home",
        "destination_ref": "place_id:cp",
        "origin_name": "home",
        "destination_name": "Connaught Place, New Delhi",
    }


def test_confirmed_plan_shows_uber_link(assistant):
    save_home(assistant)
    out = run(
        assistant.execute(
            "plan_ride",
            {"origin": "home", "destination": "place_id:cp", "confirmed": True},
        )
    )
    assert out.result["status"] == "booked_link_shown"
    ((name, card),) = out.events
    assert name == "location" and "preview" not in card
    q = parse_qs(urlparse(card["uber_url"]).query)
    assert q["action"] == ["setPickup"]
    assert q["pickup[latitude]"] == [str(HOME.lat)] and q["dropoff[nickname]"] == [
        "Connaught Place"
    ]
    assert "destination_place_id=cp" in card["maps_url"]


def test_confirmed_must_be_a_real_true(assistant):
    out = run(
        assistant.execute(
            "plan_ride",
            {
                "origin": "Connaught Place",
                "destination": "Sector 15, Noida",
                "confirmed": "yes",
            },
        )
    )
    assert out.result["status"] == "needs_confirmation"


def test_save_place_persists_and_reports_area_only(assistant, tmp_path):
    out = run(
        assistant.execute("save_place", {"label": "Office", "place": "Connaught Place"})
    )
    assert out.result == {"status": "saved", "label": "office", "area": "New Delhi"}
    assert (
        json.loads((tmp_path / "places.json").read_text())["office"]["place"]["id"]
        == "cp"
    )
    assert assistant.saved_labels() == ["office"]


def test_saving_a_whole_city_asks_for_more_detail(assistant):
    out = run(assistant.execute("save_place", {"label": "home", "place": "Faridabad"}))
    assert out.result["status"] == "too_broad"
    assert assistant.saved_labels() == []


def test_maps_failure_becomes_tool_error(tmp_path):
    a = LocationAssistant(FakeMaps(fail=True), SavedPlaces(tmp_path / "p.json"), CITIES)
    out = run(
        a.execute(
            "plan_ride",
            {"origin": "Connaught Place", "destination": "Sector 15, Noida"},
        )
    )
    assert out.result["status"] == "error" and out.events == []


# ---------- chat tool loop ----------


class ToolLLM:
    """Round 1: says something and calls plan_ride with `call_args`. Round 2: answers."""

    def __init__(self, call_args, answer):
        self.call_args = call_args
        self.answer = answer
        self.contents = []
        self.systems = []

    async def stream_turn(self, *, system, contents, tools, **kwargs):
        self.systems.append(system)
        self.contents.append(list(contents))
        if len(self.contents) == 1:
            yield "text", "ruk dekhta hu"
            call = types.FunctionCall(name="plan_ride", args=self.call_args)
            yield "call", types.Part(function_call=call)
        else:
            yield "text", self.answer


def chat(tmp_path, assistant, llm):
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=str(tmp_path))
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_location] = lambda: assistant
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def sse_events(text):
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def post(client, text, pending=None):
    body = {"persona_id": "demo-rohan", "turns": [{"role": "user", "text": text}]}
    if pending:
        body["pending_ride"] = pending
    return sse_events(client.post("/api/v1/chat/stream", json=body).text)


def test_chat_shows_draft_for_confirmation(tmp_path, assistant):
    llm = ToolLLM(
        {"origin": "Connaught Place", "destination": "Sector 15, Noida"},
        "CP se Sector 15 Noida, 34 km, 47 min. book karu? 🚗",
    )
    evs = post(chat(tmp_path, assistant, llm), "cp se sector 15 noida uber")
    names = [e for e, _ in evs]
    assert "ride_preview" in names and "location" not in names
    assert evs[-1][1]["bubbles"] == [
        "ruk dekhta hu",
        "CP se Sector 15 Noida, 34 km, 47 min. book karu? 🚗",
    ]
    # Round 2 got the model's call (with its text) and our function response back
    model_turn, tool_turn = llm.contents[1][-2:]
    assert (
        model_turn.role == "model"
        and model_turn.parts[-1].function_call.name == "plan_ride"
    )
    assert (
        tool_turn.parts[0].function_response.response["status"] == "needs_confirmation"
    )


PENDING = {
    "origin_ref": "home",
    "destination_ref": "place_id:cp",
    "origin_name": "home",
    "destination_name": "Connaught Place, New Delhi",
}


class TextLLM:
    def __init__(self, answer):
        self.answer = answer
        self.systems = []

    async def stream_turn(self, *, system, **kwargs):
        self.systems.append(system)
        yield "text", self.answer


@pytest.mark.parametrize(
    "text", ["Confirm ✅", "haan", "haan book kar do", "ok", "yes please", "theek hai"]
)
def test_plain_yes_is_confirmation(text):
    assert is_confirmation(text)


@pytest.mark.parametrize(
    "text",
    [
        "faridabad wala",
        "haan but drop change karo",
        "nahi",
        "ha",
        "",
        "kitna time lagega?",
    ],
)
def test_other_messages_are_not_confirmation(text):
    assert not is_confirmation(text)


def test_yes_confirms_pending_ride_without_the_model(tmp_path, assistant):
    save_home(assistant)
    llm = TextLLM("ready hai bhai 👍")
    evs = post(chat(tmp_path, assistant, llm), "Confirm ✅", PENDING)
    card = next(d for e, d in evs if e == "location")
    assert card["uber_url"].startswith("https://m.uber.com/ul/?action=setPickup")
    assert card["origin"]["label"] == "home"
    assert "just confirmed the pending ride" in llm.systems[0]
    assert (
        "121001" not in llm.systems[0]
    )  # result in the prompt names home by label only
    assert evs[-1][1]["bubbles"] == ["ready hai bhai 👍"]


def test_other_reply_keeps_draft_pending_for_the_model(tmp_path, assistant):
    save_home(assistant)
    llm = TextLLM("kaunsa wala bhai?")
    evs = post(chat(tmp_path, assistant, llm), "faridabad wala", PENDING)
    assert not any(e == "location" for e, _ in evs)
    assert 'origin="home", destination="place_id:cp"' in llm.systems[0]


def test_places_api_lists_and_deletes(tmp_path, assistant):
    client = chat(tmp_path, assistant, ToolLLM({}, ""))
    save_home(assistant)
    assert client.get("/api/v1/places").json() == [
        {"label": "home", "name": "Sector 21C", "address": HOME.address}
    ]
    assert client.delete("/api/v1/places/home").status_code == 204
    assert client.get("/api/v1/places").json() == []
    assert client.delete("/api/v1/places/home").status_code == 404
