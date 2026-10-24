"""Chat short forms ("r u", "pls", "h" = hai): detect them in a persona's messages and expand
them, mainly so TTS says "are you" instead of spelling "r u" (D-024)."""

import json
import logging
import re
from collections import Counter

from app.core.config import Settings
from app.ingest.models import Message
from app.llm import prompts
from app.llm.client import LLMClient
from app.persona.models import ShortForm

logger = logging.getLogger(__name__)

# Common English + Hinglish chat short forms with an unambiguous full form. Ambiguous ones
# ("n" = and/na, "m" = main/metres, "pm" = time, "bc" = also a swear) are left to the LLM,
# which sees each in context.
COMMON: dict[str, str] = {
    # English
    "r": "are", "u": "you", "ur": "your", "pls": "please", "plz": "please",
    "plzz": "please", "thx": "thanks", "thnx": "thanks", "ty": "thank you", 
    "kk": "okay", "gm": "good morning", "gn": "good night", "tc": "take care",
    "ttyl": "talk to you later", "idk": "I don't know", "btw": "by the way", "omg": "oh my god",
    "wbu": "what about you", "hbu": "how about you", "abt": "about", "bcoz": "because",
    "coz": "because", "cuz": "because", "msg": "message", "msgs": "messages",
    "bday": "birthday", "pic": "picture", "pics": "pictures", "tmrw": "tomorrow",
    "tmr": "tomorrow", "2day": "today", "2mrw": "tomorrow", "gr8": "great",
    "w8": "wait", "b4": "before", "frnd": "friend", "frnds": "friends", "gud": "good",
    "sry": "sorry", "sorryy": "sorry", "wid": "with", "wat": "what", "wt": "what",
    "nd": "and", "bt": "but", "dat": "that", "dis": "this", "ppl": "people",
    "bro": "bro", "rn": "right now", "asap": "as soon as possible", "np": "no problem",
    "nvm": "never mind", "jk": "just kidding", "lmk": "let me know", "imo": "in my opinion",
    "tbh": "to be honest",
    # Hinglish
    "h": "hai", "hn": "haan", "hnn": "haan", "nhi": "nahi", "nai": "nahi", "ni": "nahi",
    "kb": "kab", "kha": "kahan", "kaha": "kahan", "kyu": "kyun", "ky": "kya", "kr": "kar",
    "kro": "karo", "krna": "karna", "krde": "karde", "krdo": "kardo", "mtlb": "matlab",
    "yr": "yaar", "yrr": "yaar", "bhut": "bahut", "bht": "bahut", "accha": "accha",
    "acha": "accha", "thk": "theek", "tk": "theek", "shi": "sahi", "pta": "pata",
    "fir": "phir", "vo": "woh", "wo": "woh", "mai": "main", "hu": "hoon",
    "hun": "hoon", "rha": "raha", "rhi": "rahi", "rhe": "rahe", "gya": "gaya", "gyi": "gayi",
    "bhi": "bhi", "tm": "tum", "aap": "aap", "ap": "aap", "kch": "kuch", "kuch": "kuch",
}  # fmt: skip
# Entries that map to themselves are real words, listed so the LLM path never "expands" them.
COMMON = {k: v for k, v in COMMON.items() if k != v.lower()}

MIN_USES = 2
LLM_CANDIDATES = 120
_TOKEN = re.compile(r"[A-Za-z0-9']+")


def _persona_texts(messages: list[Message], sender: str) -> list[str]:
    return [m.text for m in messages if m.sender == sender]


def _example(texts: list[str], token: str) -> str:
    pattern = re.compile(rf"(?<![\w']){re.escape(token)}(?![\w'])", re.IGNORECASE)
    return next((t[:120] for t in texts if pattern.search(t)), "")


async def detect_shortforms(
    llm: LLMClient | None,
    settings: Settings,
    name: str,
    sender: str,
    messages: list[Message],
) -> list[ShortForm]:
    """Short forms the persona actually uses (>= MIN_USES), most frequent first.
    Dictionary hits always count; the LLM adds the persona's own ones, judged in context."""
    texts = _persona_texts(messages, sender)
    counts = Counter(tok.lower() for t in texts for tok in _TOKEN.findall(t))
    found: dict[str, str] = {
        tok: COMMON[tok] for tok, c in counts.items() if c >= MIN_USES and tok in COMMON
    }

    if llm is not None:
        candidates = [
            tok
            for tok, c in counts.most_common()
            if c >= MIN_USES
            and tok not in found
            and len(tok) <= 6
            and not tok.isdigit()
        ][:LLM_CANDIDATES]
        if candidates:
            blocks = "\n".join(
                f"{tok} ({counts[tok]}x): {_example(texts, tok)}" for tok in candidates
            )
            try:
                raw = await llm.generate(
                    model=settings.llm_build_model,
                    system=prompts.SHORTFORM_SYSTEM,
                    prompt=prompts.SHORTFORM_PROMPT.format(name=name, blocks=blocks),
                    json_schema=prompts.SHORTFORM_SCHEMA,
                )
                for item in json.loads(raw).get("items", []):
                    short = str(item.get("short", "")).lower().strip()
                    full = str(item.get("full", "")).strip()
                    if (
                        short in candidates
                        and full
                        and full.lower() != short
                        and len(full) <= 60
                    ):
                        found[short] = full
            except Exception:
                # Non-fatal: the dictionary results still stand. Never log message text.
                logger.exception("Short-form detection (LLM) failed for %s", name)

    return [
        ShortForm(short=tok, full=full, count=counts[tok], example=_example(texts, tok))
        for tok, full in sorted(found.items(), key=lambda kv: -counts[kv[0]])
    ]


def merge_shortforms(
    existing: list[ShortForm], detected: list[ShortForm]
) -> list[ShortForm]:
    """Re-detection keeps the user's edits (full form, enabled, hand-added) and refreshes counts."""
    by_short = {sf.short: sf for sf in existing}
    merged = []
    for sf in detected:
        if old := by_short.pop(sf.short, None):
            merged.append(
                old.model_copy(
                    update={"count": sf.count, "example": sf.example or old.example}
                )
            )
        else:
            merged.append(sf)
    return merged + list(by_short.values())


def expand_shortforms(text: str, shortforms: list[ShortForm]) -> str:
    """Replace enabled short forms with their full form (whole words, case-insensitive;
    a capitalized short form gets a capitalized full form)."""
    table = {sf.short.lower(): sf.full for sf in shortforms if sf.enabled}
    if not table or not text:
        return text
    pattern = re.compile(
        r"(?<![\w'])("
        + "|".join(map(re.escape, sorted(table, key=len, reverse=True)))
        + r")(?![\w'])",
        re.IGNORECASE,
    )

    def repl(m: re.Match) -> str:
        full = table[m.group(1).lower()]
        return full[:1].upper() + full[1:] if m.group(1)[:1].isupper() else full

    return pattern.sub(repl, text)
