"""Deterministic style statistics of the persona's own messages (FR-BLD-03)."""

import re
import statistics
from collections import Counter

import emoji
from pydantic import BaseModel

from app.ingest.models import Message

_ELONGATED = re.compile(r"(\w)\1{2,}")


class StyleStats(BaseModel):
    messages: int
    words_p50: float
    words_p90: float
    msgs_per_burst: float
    emoji_per_msg: float
    lowercase_start_pct: float
    ends_without_punct_pct: float
    elongation_pct: float
    top_emojis: list[str]


def compute_stats(messages: list[Message], sender: str, bursts: int) -> StyleStats:
    texts = [m.text for m in messages if m.sender == sender]
    words = sorted(len(t.split()) for t in texts) or [0]
    letters = [t for t in texts if t[:1].isalpha()]
    emojis = Counter(e["emoji"] for t in texts for e in emoji.emoji_list(t))
    n = max(len(texts), 1)
    return StyleStats(
        messages=len(texts),
        words_p50=statistics.median(words),
        words_p90=words[int(0.9 * (len(words) - 1))],
        msgs_per_burst=round(len(texts) / max(bursts, 1), 2),
        emoji_per_msg=round(sum(emojis.values()) / n, 2),
        lowercase_start_pct=round(
            100 * sum(t[0].islower() for t in letters) / max(len(letters), 1)
        ),
        ends_without_punct_pct=round(
            100 * sum(t.rstrip()[-1:] not in ".!?" for t in texts) / n
        ),
        elongation_pct=round(100 * sum(bool(_ELONGATED.search(t)) for t in texts) / n),
        top_emojis=[e for e, _ in emojis.most_common(8)],
    )


def describe(stats: StyleStats) -> str:
    """Hard style constraints for the reply prompt."""
    return "\n".join(
        [
            f"- Typical message: {stats.words_p50:g} words (90% are under {stats.words_p90:g}).",
            f"- Sends about {stats.msgs_per_burst:g} messages in a row per turn.",
            f"- Emojis per message: {stats.emoji_per_msg:g}. Favourites: {' '.join(stats.top_emojis) or 'none'}.",
            (
                f"- Starts lowercase {stats.lowercase_start_pct:g}% of the time; "
                f"no ending punctuation {stats.ends_without_punct_pct:g}% of the time."
            ),
            f"- Elongates words (e.g. 'okayyy') in {stats.elongation_pct:g}% of messages.",
        ]
    )
