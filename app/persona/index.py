import numpy as np

from app.persona.models import ReplyExample


class PairIndex:
    """In-memory cosine-similarity index over reply-pair contexts (D-012)."""

    def __init__(self, pairs: list[ReplyExample], vectors: np.ndarray):
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        self.pairs = pairs
        self.vectors = vectors / np.where(norms == 0, 1, norms)

    def search(self, query: list[float], k: int) -> list[ReplyExample]:
        q = np.asarray(query, dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1)
        scores = self.vectors @ q
        top = np.argsort(-scores)[: k * 2]
        seen, out = set(), []
        for i in top:  # skip duplicate replies ("haha", "ok") so examples stay varied
            reply = self.pairs[i].reply.lower()
            if reply not in seen:
                seen.add(reply)
                out.append(self.pairs[i])
            if len(out) == k:
                break
        return out
