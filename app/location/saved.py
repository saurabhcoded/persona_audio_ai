"""The user's saved places ("home", "office"…), stored locally in DATA_DIR/places.json.
Addresses are personal data: they stay on disk and go to Google only to plan a route;
the chat model sees labels, never the saved address."""

import json
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from app.location.maps import Place

# Words people use for the same saved place (Hinglish included).
ALIASES = {
    "ghar": "home",
    "house": "home",
    "my place": "home",
    "work": "office",
    "daftar": "office",
}
COMMON_LABELS = {"home", "office", "college", "school", "gym"}
_POSSESSIVE = re.compile(r"^(?:my|mera|meri|mere|apna|apni|apne)\s+", re.IGNORECASE)


def normalize_label(text: str) -> str:
    label = _POSSESSIVE.sub("", text.strip().lower())
    return ALIASES.get(label, label)


class SavedPlace(BaseModel):
    label: str
    place: Place
    saved_at: datetime


class SavedPlaces:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict[str, SavedPlace]:
        if not self.path.is_file():
            return {}
        raw = json.loads(self.path.read_text())
        return {k: SavedPlace.model_validate(v) for k, v in raw.items()}

    def all(self) -> list[SavedPlace]:
        return sorted(self._load().values(), key=lambda s: s.label)

    def get(self, label: str) -> SavedPlace | None:
        return self._load().get(normalize_label(label))

    def save(self, label: str, place: Place) -> SavedPlace:
        places = self._load()
        saved = SavedPlace(
            label=normalize_label(label), place=place, saved_at=datetime.now()
        )
        places[saved.label] = saved
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {k: v.model_dump(mode="json") for k, v in places.items()}, indent=2
            )
        )
        tmp.replace(self.path)
        return saved

    def delete(self, label: str) -> bool:
        places = self._load()
        if places.pop(normalize_label(label), None) is None:
            return False
        self.path.write_text(
            json.dumps(
                {k: v.model_dump(mode="json") for k, v in places.items()}, indent=2
            )
        )
        return True
