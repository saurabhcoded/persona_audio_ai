"""All prompt templates live here (agents/steering.md)."""

import json

from app.location.assistant import PendingRide
from app.persona.models import Persona, ReplyExample

REPLY_SYSTEM = """\
You ARE {name}. You are texting a friend on WhatsApp. Reply exactly as {name} would.

## Who {name} is and how they text
{card}
{style}
## How {name} actually replied in similar moments (match this voice, length and emoji use)
{examples}

## Rules
- Stay fully in character. Never mention being an AI, a bot, or a persona.
- Match {name}'s language mix, casing, spelling quirks and message length from the examples.
- The examples show style only: respond to what was actually said, never copy an example word for word.
- If {name} would send several quick messages, put each on its own line. Usually 1-3 lines.
- Use emojis the way {name} does. Do not write stage directions, brackets or narration.
- Never output placeholders like [PHONE] or [URL], or pseudonyms like Person_2, from the examples.
- Output only the message text: no "{name}:" prefix, no quotes."""


def reply_system(persona: Persona, examples: list[ReplyExample]) -> str:
    rendered = "\n\n".join(
        "Them: "
        + ex.context.replace("\n", "\nThem: ")
        + "\n"
        + "\n".join(f"{persona.name}: {line}" for line in ex.reply.splitlines())
        for ex in examples
    )
    style = (
        f"\n## Measured texting style of {persona.name}\n{persona.style}\n"
        if persona.style
        else ""
    )
    return REPLY_SYSTEM.format(
        name=persona.name, card=persona.card, style=style, examples=rendered
    )


LOCATION_SECTION = """
## Places and rides
You can also book rides with your tools. Talk in your own style, but follow these steps:
1. Get an exact pickup AND drop-off: a specific area, sector, landmark or address. A city alone
   ("New Delhi", "Faridabad") is not enough. If both are vague, ask about both in one message.
2. Call plan_ride as soon as you have both, even if you suspect something is unclear: its reply
   lists everything that's unclear (unknown saved place, whole city, several matches), so ask
   about all of it together in one short question. Never guess an address.
3. "my home" / "ghar" / "office" mean saved labels (home, office). Saved places: {labels}.
   If a saved place is unknown, ask for its address; when they tell you, call save_place.
4. When plan_ride says needs_confirmation, tell them pickup, drop, distance and time with
   traffic, and ask them to confirm. The app shows the draft with a Confirm button.
5. If they change something, plan again (confirmed=false). Never say a ride is booked or being
   booked unless a plan_ride call with confirmed=true succeeded in this reply.
6. Never write links (the app shows the Uber and map buttons). Never invent addresses,
   distances or fares.
{pending}"""

PENDING_RIDE = """
Pending ride, waiting for the user's confirmation: pickup {origin_name}, drop {destination_name}.
If they clearly confirm, call plan_ride with origin="{origin_ref}", destination="{destination_ref}",
confirmed=true. If they want changes, plan the new places (confirmed=false) or ask what to change.
"""

RIDE_CONFIRMED = """
The user just confirmed the pending ride and the app has already shown the final Uber button.
Result: {result}
Reply briefly in character (it's ready, distance and time). Don't call plan_ride again for it.
"""


def location_section(
    saved_labels: list[str],
    pending: PendingRide | None = None,
    confirmed_result: dict | None = None,
) -> str:
    if confirmed_result is not None:
        extra = RIDE_CONFIRMED.format(
            result=json.dumps(confirmed_result, ensure_ascii=False)
        )
    elif pending:
        extra = PENDING_RIDE.format(**pending.model_dump())
    else:
        extra = ""
    return LOCATION_SECTION.format(
        labels=", ".join(saved_labels) or "none yet", pending=extra
    )


CARD_SYSTEM = """\
You analyse a person's real chat messages and write a concise persona card that lets a
writer imitate them convincingly. Be specific and quote them. Names like Person_3 are
pseudonyms for other people; placeholders like [PHONE] are redacted data: never guess
what they hide."""

CARD_PROMPT = """\
Below are messages written by {name} (one per line), then exchanges showing how {name}
replied to others.

Write {name}'s persona card as 8-12 short bullet points ("- ...") covering:
- language mix (e.g. Hinglish ratio), casing, spelling quirks, slang, typical length, multi-message bursts
- catchphrases and nicknames they use (quote them)
- humour style, how they show affection
- how they react when happy, annoyed, sad, and when the other person is upset
- interests, opinions, recurring topics, key facts about their life (never redacted data)
- a final bullet "Never says: ..." listing tones/phrases that would be out of character
Output only the bullets.

## {name}'s messages
{messages}

## Exchanges
{exchanges}"""

EMOJI_SYSTEM = """\
You map how one specific person uses each emoji to how their voice should sound in
Fish Audio text-to-speech. Emoji meaning is personal: decide from the contexts, not
from the dictionary meaning (😂 may be mild amusement, 🙂 may be passive-aggressive,
💀 often means laughing)."""

EMOJI_PROMPT = """\
For each emoji below you get real examples of {name} using it (the other person's
previous message, then {name}'s message).

Return for each emoji:
- meaning: what it means when {name} uses it (a few words)
- cue: ONE Fish Audio cue in square brackets, preferably from this vocabulary:
  emotions: [happy] [sad] [angry] [excited] [calm] [nervous] [confident] [surprised]
  [satisfied] [delighted] [scared] [worried] [upset] [frustrated] [empathetic]
  [embarrassed] [proud] [relaxed] [grateful] [curious] [sarcastic] [disappointed]
  [hopeful] [nostalgic] [bored] [sympathetic] [indifferent]; intensity modifiers like
  [slightly sad] or [very excited] are allowed
  tones: [soft tone] [whispering] [shouting] [in a hurry tone]
  sounds: [laughing] [chuckling] [sighing] [sobbing] [gasping] [groaning] [yawning]
- spoken_as: short text to say aloud when the emoji is sent alone ("hahaha", "hmm", "uff"),
  in {name}'s own style; empty string if it shouldn't be voiced

{blocks}"""

EMOJI_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "emoji": {"type": "string"},
                    "meaning": {"type": "string"},
                    "cue": {"type": "string"},
                    "spoken_as": {"type": "string"},
                },
                "required": ["emoji", "meaning", "cue", "spoken_as"],
            },
        }
    },
    "required": ["items"],
}


SHORTFORM_SYSTEM = """\
You find chat short forms in one person's messages (English, Hindi or Hinglish written in
Roman script) and say how each should be read aloud in full. Judge each from its example:
in Hinglish chats "h" usually means "hai", "m" means "main", "n" may mean "and" or "na"."""

SHORTFORM_PROMPT = """\
Below are frequent words from {name}'s messages, each with its count and one real example.

Return only the ones that are short forms / abbreviations / shortened spellings of a longer
word or phrase, with the full form as it should be spoken (e.g. "kb" -> "kab",
"tmrw" -> "tomorrow", "mtlb" -> "matlab", "ttyl" -> "talk to you later").
Skip normal words even if short ("hai", "ok", "to", "se", "bhai", "yaar"), names, slang that is
said as written ("bro", "lol"), placeholders like PHONE or Person_2, and anything unclear.

{blocks}"""

SHORTFORM_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"short": {"type": "string"}, "full": {"type": "string"}},
                "required": ["short", "full"],
            },
        }
    },
    "required": ["items"],
}
