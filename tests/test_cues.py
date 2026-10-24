import pytest

from app.speech.cues import EmojiCue, emojis_to_cues, strip_cues, validate_cues

MAP = {
    "😂": EmojiCue(cue="[laughing]", spoken_as="hahaha"),
    "🫂": EmojiCue(cue="[soft tone][empathetic]"),
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "haan pakka 😂",
            "[joking] haan pakka",
        ),  # single laugh emoji + text: joking tone
        (
            "haan pakka 😂😂",
            "[laughing] hahaha haan pakka",
        ),  # two or more: a real laugh
        (
            "haha 😂😂!",
            "[laughing] haha!",
        ),  # existing laugh text satisfies the sound effect
        ("😂😂", "[laughing] hahaha"),  # emoji-only is spoken, not silent
        ("😂", "[laughing] hahaha"),  # a lone laugh emoji is still a laugh
        ("kya hua 🫂", "[soft tone][empathetic] kya hua"),
        ("sad hu 😢😢😢", "[very sad] sad hu"),  # default map + repetition intensity
        ("ok 👍", "[indifferent] ok"),
        ("❤️", ""),  # nothing to say
        ("no emoji here", "no emoji here"),
        ("arre 😂\nchal 🫂", "[joking] arre\n[soft tone][empathetic] chal"),
    ],
)
def test_emojis_to_cues(text, expected):
    assert emojis_to_cues(text, MAP) == expected


def test_trailing_emoji_colours_its_own_clause():
    out = emojis_to_cues("tension mat le 😂 agli baar phod dena", MAP)
    assert out == "[joking] tension mat le agli baar phod dena"


def test_persona_map_overrides_default():
    custom = {"😂": EmojiCue(cue="[embarrassed]", spoken_as="hehe")}
    assert emojis_to_cues("ok 😂", custom) == "[embarrassed] ok"


def test_single_laugh_from_persona_map_is_joking_too():
    custom = {"💀": EmojiCue(cue="[chuckling]", spoken_as="heh")}
    assert emojis_to_cues("bas kar 💀", custom) == "[joking] bas kar"
    assert emojis_to_cues("bas kar 💀💀", custom) == "[chuckling] heh bas kar"


def test_validate_converts_s1_parentheses_and_caps_cues():
    assert validate_cues("(happy) hi") == "[happy] hi"
    assert validate_cues("(not a cue) hi") == "(not a cue) hi"
    assert validate_cues("[a1][b1][c1][d1] there") == "[a1][b1][c1] there"


def test_validate_drops_overlong_cues():
    assert validate_cues(f"[{'x' * 50}] hi") == "hi"


def test_strip_cues():
    assert strip_cues("[laughing] hahaha [soft tone] yaar") == "hahaha yaar"
