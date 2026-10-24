from datetime import datetime

import pytest

from app.guardrails.output import guard_reply
from app.guardrails.pii import find_pii, redact_pii
from app.guardrails.pipeline import sanitize_chat
from app.ingest.models import Message

# All values are synthetic. 4111 1111 1111 1111 is the standard Luhn-valid test card.


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("call me on 9876543210", "PHONE"),
        ("call +91 98765 43210 now", "PHONE"),
        ("mail aman.v@example.com", "EMAIL"),
        ("pay to aman@okaxis", "UPI"),
        ("aadhaar 2345 6789 0123", "AADHAAR"),
        ("pan ABCDE1234F", "PAN"),
        ("ifsc HDFC0001234", "IFSC"),
        ("card 4111 1111 1111 1111", "CARD"),
        ("card 4111 1111 1111 1112", "ACCOUNT"),  # fails Luhn, still a long number
        ("a/c 50100123456", "ACCOUNT"),
        ("otp is 482913", "OTP"),
        ("password is hunter22", "SECRET"),
        ("see https://example.com/x", "URL"),
    ],
)
def test_pii_detected(text, label):
    assert label in find_pii(text)
    assert f"[{label}]" in redact_pii(text)


@pytest.mark.parametrize(
    "text",
    [
        "12/03/24 at 9:30",
        "haan 5 baje milte hai",
        "meet at 5 pm, 20 people",
        "haan pakka 😂",
    ],
)
def test_pii_negatives(text):
    assert redact_pii(text) == text


def msg(sender, text, minute=0):
    return Message(ts=datetime(2024, 1, 1, 10, minute), sender=sender, text=text)


def test_one_to_one_keeps_names_redacts_and_drops_artifacts():
    clean, report = sanitize_chat(
        [
            msg("Neha", "Aman number 9876543210 hai"),
            msg("Aman Verma", "<Media omitted>"),
            msg("Aman Verma", "haan Neha 😂 <This message was edited>"),
        ],
        "Aman Verma",
    )
    assert [m.sender for m in clean] == ["Neha", "Aman Verma"]
    assert clean[0].text == "Aman number [PHONE] hai"
    assert clean[1].text == "haan Neha 😂"
    assert report.artifacts_dropped == 1
    assert report.pii == {"PHONE": 1}
    assert report.participants_pseudonymized == 0


def test_group_chat_pseudonymizes_third_parties_consistently():
    clean, _ = sanitize_chat(
        [
            msg("Priya Sharma", "kal aa rahe ho?"),
            msg("+91 98765 43210", "main bhi"),
            msg("Aman Verma", "Priya tu bhi aa, bhai log bhi aa rahe"),
            msg("Bhai", "ok"),
        ],
        "Aman Verma",
    )
    assert [m.sender for m in clean] == [
        "Person_1",
        "Contact_2",
        "Aman Verma",
        "Person_3",
    ]
    # name replaced in text; the lowercase role word "bhai" survives
    assert clean[2].text == "Person_1 tu bhi aa, bhai log bhi aa rahe"


def test_guard_reply_strips_pii_and_placeholders():
    out = guard_reply("haan Person_2 ko bol\nnumber [PHONE] hai\ncall 9876543210")
    assert out == "haan ko bol\nnumber hai\ncall"
