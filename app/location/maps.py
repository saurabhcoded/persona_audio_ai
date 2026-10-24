"""Google Places API (New) + Routes API client (agents/knowledge/google-maps.md)."""

import asyncio

import google.auth
import google.auth.transport.requests
import httpx
from pydantic import BaseModel

PLACES_URL = "https://places.googleapis.com/v1/places"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
PLACE_FIELDS = "id,displayName,formattedAddress,location,types,addressComponents"


class Place(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    locality: str | None = None
    types: list[str] = []


class Route(BaseModel):
    distance_km: float
    duration_min: int  # with live traffic
    typical_min: int  # without traffic


class MapsError(RuntimeError):
    pass


def _place(raw: dict) -> Place:
    locality = next(
        (
            c["longText"]
            for c in raw.get("addressComponents", [])
            if "locality" in c.get("types", [])
        ),
        None,
    )
    return Place(
        id=raw["id"],
        name=raw.get("displayName", {}).get("text", ""),
        address=raw.get("formattedAddress", ""),
        lat=raw["location"]["latitude"],
        lng=raw["location"]["longitude"],
        locality=locality,
        types=raw.get("types", []),
    )


def _minutes(duration: str) -> int:
    return round(int(duration.rstrip("s")) / 60)


class MapsClient:
    """Authenticates with an API key if given, otherwise gcloud ADC (OAuth bearer token)."""

    def __init__(
        self,
        *,
        api_key: str | None,
        project: str | None,
        region: str,
        bias: tuple[float, float, int],
    ):
        self.api_key = api_key
        self.project = project
        self.region = region
        self.bias = bias
        self._creds = None
        self._http = httpx.AsyncClient(timeout=10)

    async def _headers(self, field_mask: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "X-Goog-FieldMask": field_mask}
        if self.api_key:
            return {**headers, "X-Goog-Api-Key": self.api_key}
        if self._creds is None:
            self._creds, adc_project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self.project = self.project or adc_project
        if not self._creds.valid:
            # Token refresh is a blocking HTTP call.
            await asyncio.to_thread(
                self._creds.refresh, google.auth.transport.requests.Request()
            )
        return {
            **headers,
            "Authorization": f"Bearer {self._creds.token}",
            "X-Goog-User-Project": self.project or "",
        }

    async def _request(self, method: str, url: str, field_mask: str, **kwargs) -> dict:
        resp = await self._http.request(
            method, url, headers=await self._headers(field_mask), **kwargs
        )
        if resp.status_code != 200:
            raise MapsError(f"{url.split('/')[-1]} returned HTTP {resp.status_code}")
        return resp.json()

    async def search(self, query: str, max_results: int = 5) -> list[Place]:
        lat, lng, radius = self.bias
        body = {
            "textQuery": query,
            "regionCode": self.region,
            "maxResultCount": max_results,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius,
                }
            },
        }
        mask = ",".join(f"places.{f}" for f in PLACE_FIELDS.split(","))
        data = await self._request("POST", f"{PLACES_URL}:searchText", mask, json=body)
        return [_place(p) for p in data.get("places", [])]

    async def get(self, place_id: str) -> Place:
        return _place(
            await self._request("GET", f"{PLACES_URL}/{place_id}", PLACE_FIELDS)
        )

    async def route(self, origin: Place, destination: Place) -> Route:
        body = {
            "origin": {"placeId": origin.id},
            "destination": {"placeId": destination.id},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
        }
        data = await self._request(
            "POST",
            ROUTES_URL,
            "routes.duration,routes.staticDuration,routes.distanceMeters",
            json=body,
        )
        if not data.get("routes"):
            raise MapsError("No driving route found")
        r = data["routes"][0]
        return Route(
            distance_km=round(r["distanceMeters"] / 1000, 1),
            duration_min=_minutes(r["duration"]),
            typical_min=_minutes(r.get("staticDuration", r["duration"])),
        )
