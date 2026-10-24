# Google Maps Platform reference (verified 2026-10-24)

## Access

- APIs enabled on project `eseller-ai` (by user approval): `places.googleapis.com` (Places API (New)),
  `routes.googleapis.com` (Routes API).
- Auth: **gcloud ADC OAuth token** — `Authorization: Bearer …` + `X-Goog-User-Project: <project>`.
  No API key needed; `GOOGLE_MAPS_API_KEY` (header `X-Goog-Api-Key`) overrides when set.
  Token refresh is blocking → `asyncio.to_thread(creds.refresh, Request())`.
- Every call needs `X-Goog-FieldMask` (only requested fields are billed).

## Calls used (`app/location/maps.py`)

| Call | Endpoint | Field mask | Latency seen |
|---|---|---|---|
| Text search | `POST https://places.googleapis.com/v1/places:searchText` `{textQuery, regionCode:"in", maxResultCount, locationBias.circle}` | `places.id,displayName,formattedAddress,location,types,addressComponents` | 0.3–1.1 s |
| Place details | `GET https://places.googleapis.com/v1/places/{id}` | same fields without `places.` | — |
| Route | `POST https://routes.googleapis.com/directions/v2:computeRoutes` `{origin.placeId, destination.placeId, travelMode:"DRIVE", routingPreference:"TRAFFIC_AWARE"}` | `routes.duration,routes.staticDuration,routes.distanceMeters` | 0.5–0.6 s |

- `duration` = with live traffic, `staticDuration` = typical; both strings like `"2813s"`.
- New Delhi → Faridabad: 33.9 km, ~47 min.

## Gotchas

- **Text search does not surface ambiguity**: "Sector 15" returns only Noida. We detect generic
  areas ourselves: if the top result's types ∩ {sublocality*, neighborhood, route} and the query
  names no city, search "<query>, <city>" for each of `LOCATION_CITIES` in parallel and offer the
  matches that are *areas* (types include political/sublocality/route) — otherwise a restaurant
  called "Connaught Place (…)" in Gurugram made CP ambiguous.
- "MG Road" in Gurugram comes back as a metro station (not an area) so only Greater Noida's MG Road
  qualifies — known limitation of the heuristic.
- Whole cities are `types: [locality, political]` → treated as too broad for a pickup/drop (D-021);
  areas (`sublocality*`, `neighborhood`, `route`) and establishments are precise enough.
- `locality` from `addressComponents` can be missing; options fall back to the searched city name.

## Uber

- No fare estimates (Uber's price API isn't available to us); we only deep-link:
  `https://m.uber.com/ul/?action=setPickup&pickup[latitude]=…&pickup[longitude]=…&pickup[nickname]=…&pickup[formatted_address]=…&dropoff[…]=…`
  (opens the app, or m.uber.com, with pickup/drop-off filled in).
- Google Maps directions link: `https://www.google.com/maps/dir/?api=1&origin=lat,lng&origin_place_id=…&destination=…&travelmode=driving`.
