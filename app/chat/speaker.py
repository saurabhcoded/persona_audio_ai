import asyncio
import base64
import logging
from collections.abc import Callable

from app.guardrails.output import guard_reply
from app.speech.cues import EmojiCue, emojis_to_cues
from app.speech.tts import TTSClient

logger = logging.getLogger(__name__)


class LineSpeaker:
    """Speaks a reply while it streams: each line (bubble) goes to TTS as soon as the
    model finishes it, in parallel with the rest of the stream. Audio comes back in
    line order via ready() (non-blocking) and drain() (waits for the rest)."""

    def __init__(
        self,
        tts: TTSClient,
        voice_id: str | None,
        emoji_map: dict[str, EmojiCue],
        audio_format: str,
        concurrency: int,
        prepare: Callable[[str], str] | None = None,
    ):
        self.tts = tts
        self.voice_id = voice_id
        self.emoji_map = emoji_map
        self.prepare = prepare or (lambda text: text)  # e.g. expand short forms
        self.audio_format = audio_format
        self._sem = asyncio.Semaphore(concurrency)
        self._pending = ""
        self._tasks: list[asyncio.Task[bytes]] = []
        self._emitted = 0

    def feed(self, text: str) -> None:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._start(line)

    def finish(self) -> None:
        self._start(self._pending)
        self._pending = ""

    def _start(self, line: str) -> None:
        # Same guard + cue conversion as the final `done` text, line by line.
        spoken = emojis_to_cues(self.prepare(guard_reply(line)), self.emoji_map)
        if spoken:
            self._tasks.append(asyncio.create_task(self._synthesize(spoken)))

    async def _synthesize(self, text: str) -> bytes:
        async with self._sem:
            return await self.tts.synthesize(text, voice_id=self.voice_id)

    def _event(self, index: int, task: asyncio.Task[bytes]) -> tuple[str, dict]:
        if task.exception() is not None:
            logger.error("TTS failed for line %d: %r", index, task.exception())
            return "audio_error", {
                "index": index,
                "message": "Voice failed for this line",
            }
        audio = base64.b64encode(task.result()).decode()
        return "audio", {"index": index, "format": self.audio_format, "audio": audio}

    def ready(self) -> list[tuple[str, dict]]:
        """Audio events that can be sent now without breaking line order."""
        events = []
        while self._emitted < len(self._tasks) and self._tasks[self._emitted].done():
            events.append(self._event(self._emitted, self._tasks[self._emitted]))
            self._emitted += 1
        return events

    async def drain(self):
        """Wait for the remaining lines, yielding their audio events in order."""
        while self._emitted < len(self._tasks):
            task = self._tasks[self._emitted]
            await asyncio.wait([task])
            yield self._event(self._emitted, task)
            self._emitted += 1

    def cancel(self) -> None:
        for task in self._tasks:
            task.cancel()
