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
        return stored + [self._builtin(pid) for pid in BUILTIN]

    def _overrides_path(self) -> Path:
        return self.root / "builtin_overrides.json"

    def _builtin(self, persona_id: str) -> Persona:
        """Built-in (demo) personas live in code; user changes (voice) are stored beside them."""
        path = self._overrides_path()
        overrides = (
            json.loads(path.read_text()).get(persona_id) if path.is_file() else None
        )
        base = BUILTIN[persona_id].model_dump(mode="json")
        return Persona.model_validate(base | (overrides or {}))

    def update(self, persona_id: str, fields: dict) -> Persona:
        """Change user-editable fields (JSON-able values). Built-in personas keep the
        changes in builtin_overrides.json since their definition lives in code."""
        if persona_id in BUILTIN:
            path = self._overrides_path()
            overrides = json.loads(path.read_text()) if path.is_file() else {}
            overrides.setdefault(persona_id, {}).update(fields)
            self.root.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False))
            return self._builtin(persona_id)
        persona = Persona.model_validate(
            self.get(persona_id).model_dump(mode="json") | fields
        )
        self.save(persona)
        return persona

    def set_voice(self, persona_id: str, voice_id: str | None) -> Persona:
        return self.update(persona_id, {"voice_id": voice_id})

    def load_messages(self, persona_id: str) -> list[Message]:
        """Sanitized messages saved at build time (empty for built-in personas)."""
        if persona_id in BUILTIN:
            return []
        path = self._dir(persona_id) / "messages.jsonl"
        if not path.is_file():
            return []
        return [
            Message.model_validate_json(line) for line in path.read_text().splitlines()
        ]

    def get(self, persona_id: str) -> Persona:
        if persona_id in BUILTIN:
            return self._builtin(persona_id)
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
