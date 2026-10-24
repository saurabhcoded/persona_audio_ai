"""All prompt templates live here (agents/steering.md)."""

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
