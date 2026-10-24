"""On-disk persona repository: data/personas/<id>/ (technical-design.md §3).
Only sanitized data is ever written here."""

import json
import re
import shutil
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import Depends, HTTPException

from app.core.config import Settings, get_settings
from app.ingest.models import Message
from app.persona.demo import PERSONAS as BUILTIN
from app.persona.index import PairIndex
from app.persona.models import Persona, ReplyExample


class PersonaStore:
    def __init__(self, root: Path):
        self.root = root / "personas"
        self._indexes: dict[str, tuple[float, PairIndex]] = {}

    def _dir(self, persona_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9-]{1,64}", persona_id):
            raise HTTPException(status_code=404, detail="Persona not found")
        return self.root / persona_id

    def new_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "persona"
        return f"{slug}-{uuid.uuid4().hex[:6]}"

    def all(self) -> list[Persona]:
        stored = []
        if self.root.is_dir():
            for path in self.root.glob("*/persona.json"):
                stored.append(Persona.model_validate_json(path.read_text()))
        stored.sort(
            key=lambda p: p.created_at.timestamp() if p.created_at else 0, reverse=True
        )
        return stored + list(BUILTIN.values())

    def get(self, persona_id: str) -> Persona:
        if persona_id in BUILTIN:
            return BUILTIN[persona_id]
        path = self._dir(persona_id) / "persona.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Persona not found")
        return Persona.model_validate_json(path.read_text())

    def save(self, persona: Persona) -> None:
        d = self._dir(persona.id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "persona.json.tmp"
        tmp.write_text(persona.model_dump_json(indent=2))
        tmp.replace(d / "persona.json")

    def save_messages(self, persona_id: str, messages: list[Message]) -> None:
        with (self._dir(persona_id) / "messages.jsonl").open("w") as f:
            for m in messages:
                f.write(m.model_dump_json() + "\n")

    def save_index(
        self, persona_id: str, pairs: list[ReplyExample], vectors: np.ndarray
    ) -> None:
        d = self._dir(persona_id)
        with (d / "pairs.jsonl").open("w") as f:
            for p in pairs:
                f.write(p.model_dump_json() + "\n")
        np.save(d / "vectors.npy", vectors.astype(np.float32))

    def load_index(self, persona_id: str) -> PairIndex | None:
        """Cached by file mtime, so a rebuild is picked up without a restart."""
        if persona_id in BUILTIN:
            return None
        vec_path = self._dir(persona_id) / "vectors.npy"
        if not vec_path.is_file():
            return None
        mtime = vec_path.stat().st_mtime
        cached = self._indexes.get(persona_id)
        if cached and cached[0] == mtime:
            return cached[1]
        pairs = [
            ReplyExample.model_validate(json.loads(line))
            for line in (vec_path.parent / "pairs.jsonl").read_text().splitlines()
        ]
        index = PairIndex(pairs, np.load(vec_path))
        self._indexes[persona_id] = (mtime, index)
        return index

    def delete(self, persona_id: str) -> None:
        if persona_id in BUILTIN:
            raise HTTPException(
                status_code=400, detail="The demo persona can't be deleted"
            )
        d = self._dir(persona_id)
        if not d.is_dir():
            raise HTTPException(status_code=404, detail="Persona not found")
        shutil.rmtree(d)
        self._indexes.pop(persona_id, None)


@lru_cache
def _store(data_dir: str) -> PersonaStore:
    return PersonaStore(Path(data_dir))


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> PersonaStore:
    return _store(settings.data_dir)


StoreDep = Annotated[PersonaStore, Depends(get_store)]
