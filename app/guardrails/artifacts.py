import re

from app.ingest.models import Message

_DROP = re.compile(
    r"^(?:<media omitted>"
    r"|(?:image|video|audio|sticker|gif|document|contact card|media) omitted"
    r"|<attached: [^>]*>"
    r"|.*\(file attached\)"
    r"|this message was deleted|you deleted this message"
    r"|waiting for this message.*"
    r"|missed (?:voice|video) call.*"
    r"|location: https?://\S+"
    r"|live location shared"
    r"|null)$",
    re.IGNORECASE | re.DOTALL,
)
_EDITED = re.compile(r"\s*<this message was edited>\s*$", re.IGNORECASE)


def drop_artifacts(messages: list[Message]) -> tuple[list[Message], int]:
    """Remove media placeholders, deleted messages and call notices; strip the edited marker."""
    kept = []
    for m in messages:
        text = _EDITED.sub("", m.text).strip()
        if not text or _DROP.match(text):
            continue
        kept.append(m if text == m.text else m.model_copy(update={"text": text}))
    return kept, len(messages) - len(kept)
