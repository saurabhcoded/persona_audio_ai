"""WhatsApp chat export parser (Android and iOS formats). See agents/workflows/ingestion-pipeline.md."""

import io
import re
import zipfile
from collections import Counter
from datetime import datetime

from app.ingest.models import Message

# Direction marks and BOM that iOS/Android sprinkle into exports
_INVISIBLE = dict.fromkeys(
    [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0xFEFF]
)

_STAMP = (
    r"(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+"
    r"(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
    r"(?:[\s\u202f]*(?P<ampm>[ap]\.?\s?m\.?))?"
)
_ANDROID = re.compile(rf"^{_STAMP}\s+-\s+(?P<rest>.*)$", re.IGNORECASE)
_IOS = re.compile(rf"^\[{_STAMP}\]\s+(?P<rest>.*)$", re.IGNORECASE)
_SENDER = re.compile(r"^(?P<sender>[^:]{1,80}?):\s(?P<text>.*)$", re.DOTALL)


class ExportError(ValueError):
    """The upload isn't a readable WhatsApp chat export."""


def read_export(data: bytes, filename: str = "") -> str:
    """Return the chat text from a .txt export or a .zip export (which contains _chat.txt)."""
    if data[:2] == b"PK" or filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                txts = [i for i in zf.infolist() if i.filename.lower().endswith(".txt")]
                if not txts:
                    raise ExportError("The zip has no chat .txt file")
                member = max(txts, key=lambda i: i.file_size)
                data = zf.read(member)
        except zipfile.BadZipFile as e:
            raise ExportError("Not a valid zip file") from e
    return data.decode("utf-8-sig", errors="replace")


def _date_order(dates: list[str]) -> str:
    """'dmy' or 'mdy', from whichever field ever exceeds 12. Defaults to dmy (India)."""
    for d in dates:
        a, b, _ = re.split(r"[/.-]", d)
        if int(a) > 12:
            return "dmy"
        if int(b) > 12:
            return "mdy"
    return "dmy"


def _to_datetime(date: str, time: str, ampm: str | None, order: str) -> datetime:
    a, b, y = (int(x) for x in re.split(r"[/.-]", date))
    day, month = (a, b) if order == "dmy" else (b, a)
    year = y + 2000 if y < 100 else y
    parts = [int(x) for x in re.split(r"[:.]", time)]
    hour, minute, second = parts[0], parts[1], parts[2] if len(parts) > 2 else 0
    if ampm:
        pm = ampm.lower().replace(".", "").replace(" ", "") == "pm"
        hour = hour % 12 + (12 if pm else 0)
    return datetime(year, month, day, hour, minute, second)


def parse_whatsapp(text: str) -> list[Message]:
    """Parse an export into messages. System lines (no "Name: ") are skipped;
    lines without a timestamp continue the previous message."""
    entries: list[dict] = []
    for raw in text.splitlines():
        line = raw.translate(_INVISIBLE)
        m = _ANDROID.match(line) or _IOS.match(line)
        if m:
            entries.append(m.groupdict())
        elif entries:
            entries[-1]["rest"] += "\n" + line
    if not entries:
        raise ExportError(
            "No WhatsApp messages found. Export the chat as .txt (without media)"
        )

    order = _date_order([e["date"] for e in entries])
    messages = []
    for e in entries:
        sm = _SENDER.match(e["rest"])
        if not sm:
            continue  # system line: "X joined", encryption notice, ...
        try:
            ts = _to_datetime(e["date"], e["time"], e["ampm"], order)
        except ValueError:
            continue
        messages.append(
            Message(ts=ts, sender=sm["sender"].strip(), text=sm["text"].strip())
        )
    if not messages:
        raise ExportError("No messages with a sender found in the export")
    return messages


def participants(messages: list[Message]) -> Counter[str]:
    return Counter(m.sender for m in messages)
