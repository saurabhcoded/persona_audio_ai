"""Location assist: tools the chat model can call to plan rides and save places.

A ride is two-step: plan_ride(confirmed=false) shows a draft (pickup, drop, distance, time)
for the user to check; only plan_ride(confirmed=true) shows the Open-in-Uber link (D-021).

The model only sees labels, place names and route numbers; full saved addresses and the
deep links go to the UI as SSE events (D-019)."""

import asyncio
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.location.maps import MapsClient, Place
from app.location.saved import COMMON_LABELS, SavedPlaces, normalize_label

logger = logging.getLogger(__name__)

# Place types that name an area many cities share ("Sector 15", "MG Road").
GENERIC_TYPES = {
    "sublocality",
    "sublocality_level_1",
    "sublocality_level_2",
    "neighborhood",
    "route",
}
# Too broad for a pickup/drop-off: a whole city, district or PIN code.
BROAD_TYPES = {
    "locality",
    "administrative_area_level_1",
    "administrative_area_level_2",
    "administrative_area_level_3",
    "country",
    "postal_code",
    "colloquial_area",
}
CITY_ALIASES = {"gurgaon": "gurugram", "delhi": "new delhi"}
# A message made only of these words confirms a pending ride (needs one of STRONG_YES).
YES_WORDS = {
    "confirm", "confirmed", "haan", "haa", "han", "yes", "yep", "ok", "okay", "book", "kar",
    "karo", "do", "de", "done", "theek", "thik", "hai", "chalo", "perfect", "sahi", "bhai",
    "yaar", "please", "pls", "ji", "it", "go", "ahead",
}  # fmt: skip
STRONG_YES = {
    "confirm", "confirmed", "haan", "haa", "han", "yes", "yep", "ok", "okay", "book", "done",
    "theek", "thik", "chalo", "perfect", "sahi",
}  # fmt: skip


def is_confirmation(text: str) -> bool:
    """True for a short, plain yes ("Confirm ✅", "haan book kar do", "ok"). Anything with
    other content ("faridabad wala", "haan but drop change") is left to the model."""
    words = re.findall(r"[a-z]+", text.lower())
    return (
        0 < len(words) <= 6
        and set(words) <= YES_WORDS
        and bool(set(words) & STRONG_YES)
    )


TOOLS = [
    {
        "name": "plan_ride",
        "description": (
            "Plan a cab/Uber ride between two places. Reports anything unclear about the pickup "
            "or drop-off (unknown saved place, a whole city instead of an exact spot, several "
            "matches). When both are clear: with confirmed=false it shows the user a draft "
            "(pickup, drop, distance, time with traffic) to confirm; with confirmed=true it "
            "shows the final 'Open in Uber' button. Use it for Uber/cab/ride/directions or "
            "how far / how long to go somewhere."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": (
                        "Pickup: a saved place label ('home', 'office'), a place the user named "
                        "('New Delhi', 'Sector 15, Faridabad'), or an option exactly as returned "
                        "by a previous call."
                    ),
                },
                "destination": {
                    "type": "string",
                    "description": "Drop-off, same forms as origin.",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": (
                        "false (default) = show a draft for the user to check. true only after "
                        "the user explicitly confirmed that draft."
                    ),
                },
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "save_place",
        "description": (
            "Save a place under a label (home, office, …) so the user can later say 'from my "
            "home'. Call it after the user tells you the address."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "e.g. home, office, gym"},
                "place": {
                    "type": "string",
                    "description": "The address or place name the user gave",
                },
            },
            "required": ["label", "place"],
        },
    },
]


class Resolution(BaseModel):
    status: Literal["ok", "ambiguous", "unknown_saved_place", "too_broad", "not_found"]
    query: str
    place: Place | None = None
    label: str | None = None  # saved-place label, when resolved from one
    options: list[Place] = []

    def option_text(self, p: Place) -> str:
        return (
            f"{p.name}, {p.locality}"
            if p.locality and p.locality not in p.name
            else p.name
        )

    def for_model(self) -> dict:
        if self.status == "ambiguous":
            return {
                "status": "ambiguous",
                "query": self.query,
                "options": [self.option_text(p) for p in self.options],
            }
        if self.status == "unknown_saved_place":
            return {"status": "unknown_saved_place", "label": self.label}
        if self.status == "too_broad":
            return {
                "status": "too_broad",
                "query": self.query,
                "ask_for": f"a specific area, sector, landmark or address in {self.place.name}",
            }
        return {"status": self.status, "query": self.query}


class PendingRide(BaseModel):
    """A draft ride awaiting the user's confirmation. The client keeps it (from the
    `ride_preview` event) and sends it back with the next message, so "haan" confirms
    exactly the places the user checked."""

    origin_ref: str = Field(max_length=200)
    destination_ref: str = Field(max_length=200)
    origin_name: str = Field(max_length=200)
    destination_name: str = Field(max_length=200)


class ToolOutcome(BaseModel):
    result: dict  # sent back to the model
    events: list[tuple[str, dict]] = []  # sent to the UI


def uber_link(origin: Place, destination: Place) -> str:
    """Uber universal link: opens the app (or m.uber.com) with pickup and drop-off filled in."""
    params = {"action": "setPickup"}
    for key, p in (("pickup", origin), ("dropoff", destination)):
        params |= {
            f"{key}[latitude]": p.lat,
            f"{key}[longitude]": p.lng,
            f"{key}[nickname]": p.name,
            f"{key}[formatted_address]": p.address,
        }
    return "https://m.uber.com/ul/?" + urlencode(params, safe="[]")


def maps_link(origin: Place, destination: Place) -> str:
    params = {
        "api": 1,
        "origin": f"{origin.lat},{origin.lng}",
        "origin_place_id": origin.id,
        "destination": f"{destination.lat},{destination.lng}",
        "destination_place_id": destination.id,
        "travelmode": "driving",
    }
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def _card_place(r: Resolution) -> dict:
    p = r.place
    return {"label": r.label, "name": p.name, "address": p.address}


def _ref(r: Resolution) -> str:
    """How the model refers to a resolved place in the confirming call."""
    return r.label or f"place_id:{r.place.id}"


def _model_name(r: Resolution) -> str:
    """Saved places by label only: the model never sees the saved address."""
    if r.label:
        return r.label
    p = r.place
    return (
        f"{p.name}, {p.locality}" if p.locality and p.locality not in p.name else p.name
    )


class LocationAssistant:
    def __init__(self, maps: MapsClient, saved: SavedPlaces, cities: list[str]):
        self.maps = maps
        self.saved = saved
        self.cities = cities

    def saved_labels(self) -> list[str]:
        return [s.label for s in self.saved.all()]

    def _mentions_city(self, query: str) -> bool:
        q = query.lower()
        names = (
            {c.lower() for c in self.cities}
            | set(CITY_ALIASES)
            | set(CITY_ALIASES.values())
        )
        return "," in q or any(name in q for name in names)

    async def _city_options(self, query: str) -> list[Place]:
        results = await asyncio.gather(
            *(
                self.maps.search(f"{query}, {city}", max_results=1)
                for city in self.cities
            ),
            return_exceptions=True,
        )
        options, seen = [], set()
        for city, found in zip(self.cities, results, strict=True):
            if isinstance(found, BaseException) or not found:
                continue
            p = found[0]
            city_word = city.split()[-1].lower()
            is_area = bool(
                set(p.types) & (GENERIC_TYPES | {"political"})
            )  # not a shop named after it
            if (
                p.id not in seen
                and is_area
                and p.name.lower().startswith(query.lower())
                and city_word in p.address.lower()
            ):
                seen.add(p.id)
                options.append(
                    p if p.locality else p.model_copy(update={"locality": city})
                )
        return options

    async def resolve(self, text: str, *, allow_saved: bool = True) -> Resolution:
        query = text.strip()
        if query.startswith("place_id:"):
            return Resolution(
                status="ok", query=query, place=await self.maps.get(query[9:])
            )
        if allow_saved:
            if saved := self.saved.get(query):
                return Resolution(
                    status="ok", query=query, place=saved.place, label=saved.label
                )
            if normalize_label(query) in COMMON_LABELS:
                return Resolution(
                    status="unknown_saved_place",
                    query=query,
                    label=normalize_label(query),
                )
        results = await self.maps.search(query)
        if not results:
            return Resolution(status="not_found", query=query)
        top = results[0]
        if set(top.types) & GENERIC_TYPES and not self._mentions_city(query):
            options = await self._city_options(query)
            if len(options) >= 2:
                return Resolution(status="ambiguous", query=query, options=options)
            if options:
                top = options[0]
        types = set(top.types)
        if types & BROAD_TYPES and not types & GENERIC_TYPES:
            return Resolution(status="too_broad", query=query, place=top)
        return Resolution(status="ok", query=query, place=top)

    async def plan_ride(
        self, origin: str, destination: str, confirmed: bool = False
    ) -> ToolOutcome:
        o, d = await asyncio.gather(self.resolve(origin), self.resolve(destination))
        unresolved = {
            role: r
            for role, r in (("origin", o), ("destination", d))
            if r.status != "ok"
        }
        if unresolved:
            events = [
                ("choices", {"options": [r.option_text(p) for p in r.options]})
                for r in unresolved.values()
                if r.status == "ambiguous"
            ][:1]
            result = {"status": "need_info"} | {
                role: r.for_model() for role, r in unresolved.items()
            }
            return ToolOutcome(result=result, events=events)

        route = await self.maps.route(o.place, d.place)
        card = {
            "kind": "ride",
            "origin": _card_place(o),
            "destination": _card_place(d),
            "distance_km": route.distance_km,
            "duration_min": route.duration_min,
            "typical_min": route.typical_min,
        }
        summary = {
            "from": _model_name(o),
            "to": _model_name(d),
            "distance_km": route.distance_km,
            "duration_min_with_traffic": route.duration_min,
            "typical_duration_min": route.typical_min,
        }
        if not confirmed:
            # Draft first: the user checks pickup and drop before any booking link appears.
            draft = {
                "origin_ref": _ref(o),
                "destination_ref": _ref(d),
                "origin_name": _model_name(o),
                "destination_name": _model_name(d),
            }
            result = {
                "status": "needs_confirmation",
                **summary,
                "next": (
                    "Tell the user pickup, drop, distance and time and ask them to confirm. "
                    "Call plan_ride again with confirmed=true only after they say yes."
                ),
            }
            # The UI shows a Confirm / Cancel bar for the draft; see is_confirmation().
            events = [("ride_preview", card | {"preview": True, "draft": draft})]
            return ToolOutcome(result=result, events=events)

        card |= {
            "uber_url": uber_link(o.place, d.place),
            "maps_url": maps_link(o.place, d.place),
        }
        result = {"status": "booked_link_shown", **summary}
        return ToolOutcome(result=result, events=[("location", card)])

    async def save_place(self, label: str, place: str) -> ToolOutcome:
        r = await self.resolve(place, allow_saved=False)
        if r.status != "ok":
            events = (
                [("choices", {"options": [r.option_text(p) for p in r.options]})]
                if r.status == "ambiguous"
                else []
            )
            return ToolOutcome(result=r.for_model(), events=events)
        saved = self.saved.save(label, r.place)
        event = {"label": saved.label, "name": r.place.name, "address": r.place.address}
        result = {
            "status": "saved",
            "label": saved.label,
            "area": r.place.locality or r.place.name,
        }
        return ToolOutcome(result=result, events=[("saved_place", event)])

    async def execute(self, name: str, args: dict) -> ToolOutcome:
        try:
            if name == "plan_ride":
                return await self.plan_ride(
                    str(args.get("origin", "")),
                    str(args.get("destination", "")),
                    confirmed=args.get("confirmed") is True,
                )
            if name == "save_place":
                return await self.save_place(
                    str(args.get("label", "")), str(args.get("place", ""))
                )
            return ToolOutcome(
                result={"status": "error", "message": f"unknown tool {name}"}
            )
        except Exception:
            # Never log the places themselves (they can be home addresses).
            logger.exception("Location tool %s failed", name)
            return ToolOutcome(
                result={"status": "error", "message": "location service unavailable"}
            )


@lru_cache
def _assistant(
    data_dir: str,
    api_key: str | None,
    project: str | None,
    region: str,
    bias: tuple[float, float, int],
    cities: tuple[str, ...],
) -> LocationAssistant:
    maps = MapsClient(api_key=api_key, project=project, region=region, bias=bias)
    return LocationAssistant(
        maps, SavedPlaces(Path(data_dir) / "places.json"), list(cities)
    )


def get_location(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LocationAssistant | None:
    if not settings.location_assist:
        return None
    return _assistant(
        settings.data_dir,
        settings.google_maps_api_key,
        settings.gcp_project,
        settings.location_region,
        (
            settings.location_bias_lat,
            settings.location_bias_lng,
            settings.location_bias_radius_m,
        ),
        tuple(settings.location_cities),
    )


LocationDep = Annotated[LocationAssistant | None, Depends(get_location)]
