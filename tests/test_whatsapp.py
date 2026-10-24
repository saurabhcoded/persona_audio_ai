import io
import zipfile
from datetime import datetime

import pytest

from app.ingest.whatsapp import ExportError, parse_whatsapp, participants, read_export

NNBSP = " "
LRM = "‎"

ANDROID = f"""\
12/03/24, 9:00{NNBSP}pm - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.
12/03/24, 9:01{NNBSP}pm - Neha: kal match chalein?
12/03/24, 9:02{NNBSP}pm - Aman Verma: haan pakka 😂
second line of the same message
13/03/24, 10:15{NNBSP}am - Aman Verma: <Media omitted>
13/03/24, 10:16{NNBSP}am - Neha joined using this group's invite link
"""

IOS = f"""\
{LRM}[3/12/24, 21:01:05] Neha: kal match chalein?
[3/13/24, 9:02:00 PM] Aman Verma: haan pakka 😂
"""


def test_android_12h_multiline_and_system_lines():
    msgs = parse_whatsapp(ANDROID)
    assert [m.sender for m in msgs] == ["Neha", "Aman Verma", "Aman Verma"]
    assert msgs[0].ts == datetime(2024, 3, 12, 21, 1)
    assert msgs[1].text == "haan pakka 😂\nsecond line of the same message"
    assert msgs[2].ts == datetime(2024, 3, 13, 10, 15)


def test_ios_brackets_seconds_lrm_and_month_first():
    msgs = parse_whatsapp(IOS)
    assert [m.sender for m in msgs] == ["Neha", "Aman Verma"]
    assert msgs[0].ts == datetime(2024, 3, 12, 21, 1, 5)  # 13 in 2nd field => M/D/Y
    assert msgs[1].ts == datetime(2024, 3, 13, 21, 2, 0)


def test_24h_android():
    msgs = parse_whatsapp("25/12/2023, 18:30 - Neha: merry xmas\n")
    assert msgs[0].ts == datetime(2023, 12, 25, 18, 30)


def test_participants_counts():
    assert participants(parse_whatsapp(ANDROID)) == {"Aman Verma": 2, "Neha": 1}


def test_read_export_zip_picks_chat_txt():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("_chat.txt", ANDROID)
        zf.writestr("note.txt", "x")
    assert "kal match" in read_export(buf.getvalue(), "export.zip")


def test_garbage_raises():
    with pytest.raises(ExportError):
        parse_whatsapp("hello\nthis is not a chat\n")
