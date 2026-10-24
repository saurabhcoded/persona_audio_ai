"""Turn persona text (with emojis) into Fish Audio S2 TTS text with bracket cues.

See agents/knowledge/fish-audio.md for the cue syntax and agents/workflows/chat-pipeline.md
for the rules implemented here.
"""

import re
from collections import Counter

import emoji
from pydantic import BaseModel


class EmojiCue(BaseModel):
    """How one emoji should sound when spoken."""

    cue: str  # e.g. "[laughing]"
    spoken_as: str = ""  # said aloud when the emoji stands alone, e.g. "hahaha"


# Fallback when the persona's own emoji map has no entry (D-003: persona map wins).
DEFAULT_EMOJI_MAP: dict[str, EmojiCue] = {
    "😂": EmojiCue(cue="[laughing]", spoken_as="hahaha"),
    "🤣": EmojiCue(cue="[laughing]", spoken_as="hahahaha"),
    "💀": EmojiCue(cue="[laughing]", spoken_as="hahaha"),
    "😅": EmojiCue(cue="[embarrassed]", spoken_as="hehe"),
    "😆": EmojiCue(cue="[chuckling]", spoken_as="haha"),
    "😁": EmojiCue(cue="[happy]"),
    "😊": EmojiCue(cue="[happy]"),
    "🙂": EmojiCue(cue="[calm]"),
    "😍": EmojiCue(cue="[delighted]"),
    "🥰": EmojiCue(cue="[warm and happy]"),
    "❤️": EmojiCue(cue="[warm and happy]"),
    "🤗": EmojiCue(cue="[warm and happy]"),
    "🥲": EmojiCue(cue="[smiling but sad]"),
    "😢": EmojiCue(cue="[sad]"),
    "😭": EmojiCue(cue="[sobbing]", spoken_as="uff"),
    "😔": EmojiCue(cue="[disappointed]"),
    "🥺": EmojiCue(cue="[soft tone]", spoken_as="pleasee"),
    "😡": EmojiCue(cue="[angry]"),
    "😠": EmojiCue(cue="[angry]"),
    "😤": EmojiCue(cue="[frustrated]"),
    "🤦": EmojiCue(cue="[frustrated]", spoken_as="uff"),
    "🙄": EmojiCue(cue="[sarcastic]", spoken_as="ugh"),
    "😏": EmojiCue(cue="[sarcastic]"),
    "😉": EmojiCue(cue="[playful]"),
    "😎": EmojiCue(cue="[confident]"),
    "💪": EmojiCue(cue="[confident]"),
    "🔥": EmojiCue(cue="[excited]"),
    "🎉": EmojiCue(cue="[excited]"),
    "😮": EmojiCue(cue="[surprised]", spoken_as="whoa"),
    "😱": EmojiCue(cue="[scared]", spoken_as="what"),
    "😬": EmojiCue(cue="[nervous]"),
    "🤔": EmojiCue(cue="[curious]", spoken_as="hmm"),
    "😴": EmojiCue(cue="[yawning]", spoken_as="aah"),
    "🫂": EmojiCue(cue="[compassionate]"),
    "🙏": EmojiCue(cue="[grateful]", spoken_as="thank you"),
    "👍": EmojiCue(cue="[indifferent]", spoken_as="okay"),
}

# Sound-effect cues must be followed by matching text (Fish docs).
SOUND_EFFECTS = {
    "laughing", "laughing loudly", "chuckling", "sobbing", "crying loudly", "sighing", "groaning",
    "panting", "gasping", "yawning", "snoring", "clear throat",
}  # fmt: skip

# S1-style "(happy)" cues we convert to S2 "[happy]".
_KNOWN_CUE_WORDS = SOUND_EFFECTS | {
    "happy", "sad", "angry", "excited", "calm", "nervous", "confident", "surprised",
    "scared", "worried", "upset", "frustrated", "empathetic", "embarrassed", "sarcastic",
    "whispering", "shouting", "screaming", "soft tone", "in a hurry tone", "emphasis",
    "break", "long-break",
}  # fmt: skip

MAX_CUES_PER_SENTENCE = 3
MAX_CUE_CHARS = 40

_CUE = re.compile(r"\[[^\[\]]*\]")
_SENTENCE_END = re.compile(r"[.!?]+(?=\s)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_LAUGH_TEXT = re.compile(r"\b(?:h[ae]){2,}h?\b|\blol\b", re.IGNORECASE)
_S1_CUE = re.compile(r"\(([a-z][a-z -]{1,30})\)", re.IGNORECASE)
_SPACES = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([!?.,])")


def _norm(e: str) -> str:
    return e.replace("️", "")


def _lookup(e: str, emoji_map: dict[str, EmojiCue]) -> EmojiCue | None:
    for table in (emoji_map, DEFAULT_EMOJI_MAP):
        for key, value in table.items():
            if _norm(key) == _norm(e):
                return value
    return None


def _clauses(line: str) -> list[str]:
    """Split a line at sentence punctuation and after each run of emojis, so a trailing
    emoji colours the clause it ends."""
    cuts = {m.end() for m in _SENTENCE_END.finditer(line)}
    found = emoji.emoji_list(line)
    for i, e in enumerate(found):
        next_start = found[i + 1]["match_start"] if i + 1 < len(found) else len(line)
        if i + 1 == len(found) or line[e["match_end"] : next_start].strip():
            cuts.add(e["match_end"])
    parts, prev = [], 0
    for cut in sorted(cuts | {len(line)}):
        part = line[prev:cut].strip()
        prev = cut
        if not part:
            continue
        if (
            parts
            and not any(c.isalnum() for c in emoji.replace_emoji(part, ""))
            and not emoji.emoji_count(part)
        ):
            parts[-1] += part  # stray punctuation
        else:
            parts.append(part)
    return parts


def _cue_name(cue: str) -> str:
    return cue.strip("[]").strip().lower()


def _intensify(cue: str) -> str:
    name = _cue_name(cue)
    if "][" in cue or name in SOUND_EFFECTS or name.startswith(("very ", "extremely ")):
        return cue
    return f"[very {name}]"


def _clause_to_tts(clause: str, emoji_map: dict[str, EmojiCue]) -> str:
    text = _SPACE_BEFORE_PUNCT.sub(
        r"\1", _SPACES.sub(" ", emoji.replace_emoji(clause, ""))
    ).strip()
    found = [e["emoji"] for e in emoji.emoji_list(clause)]
    if not found:
        return text
    top, count = Counter(_norm(e) for e in found).most_common(1)[0]
    info = _lookup(top, emoji_map)
    if info is None:
        return text
    cue = _intensify(info.cue) if count >= 3 else info.cue
    body = text
    if (
        _cue_name(cue) in SOUND_EFFECTS
        and info.spoken_as
        and not _LAUGH_TEXT.search(text)
    ):
        body = f"{info.spoken_as} {text}".strip()
    elif not body:
        body = info.spoken_as
    if not body:
        return ""  # e.g. a lone ❤️ with nothing to say
    return f"{cue} {body}"


def emojis_to_cues(text: str, emoji_map: dict[str, EmojiCue] | None = None) -> str:
    """Persona text with emojis -> TTS text with S2 cues at clause starts, emojis removed."""
    emoji_map = emoji_map or {}
    lines = []
    for line in text.splitlines():
        spoken = [s for c in _clauses(line) if (s := _clause_to_tts(c, emoji_map))]
        if spoken:
            lines.append(" ".join(spoken))
    return validate_cues("\n".join(lines))


def validate_cues(text: str) -> str:
    """Enforce S2 cue rules: brackets not parentheses, short cues, at most 3 per sentence."""
    text = _S1_CUE.sub(
        lambda m: (
            f"[{m.group(1)}]" if m.group(1).lower() in _KNOWN_CUE_WORDS else m.group(0)
        ),
        text,
    )
    text = _CUE.sub(
        lambda m: m.group(0) if 2 < len(m.group(0)) <= MAX_CUE_CHARS else "", text
    )
    out_lines = []
    for line in text.splitlines():
        sentences = []
        for sentence in _SENTENCE_SPLIT.split(line):
            cues = _CUE.findall(sentence)
            for extra in cues[MAX_CUES_PER_SENTENCE:]:
                sentence = sentence.replace(extra, "", 1)
            sentences.append(_SPACES.sub(" ", sentence).strip())
        out_lines.append(" ".join(s for s in sentences if s))
    return "\n".join(line for line in out_lines if line)


def strip_cues(text: str) -> str:
    """Remove bracket cues, for anything shown in the UI."""
    return _SPACES.sub(" ", _CUE.sub("", text)).strip()
