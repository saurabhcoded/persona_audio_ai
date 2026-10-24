const MIME = { mp3: "audio/mpeg", wav: "audio/wav", opus: "audio/ogg" };

export function base64ToBlob(b64, format = "mp3") {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: MIME[format] ?? "audio/mpeg" });
}

// Plays audio clips back to back, in the order they were queued.
// onChange(ownerId | null) reports which message is currently speaking.
export class AudioQueue {
  constructor(onChange) {
    this.onChange = onChange;
    this.queue = [];
    this.current = null;
  }

  enqueue(blob, ownerId) {
    this.queue.push({ blob, ownerId });
    if (!this.current) this.#next();
  }

  stop() {
    this.queue = [];
    if (this.current) {
      this.current.audio.pause();
      URL.revokeObjectURL(this.current.url);
      this.current = null;
    }
    this.onChange(null);
  }

  #next() {
    const item = this.queue.shift();
    if (!item) {
      this.current = null;
      this.onChange(null);
      return;
    }
    const url = URL.createObjectURL(item.blob);
    const audio = new Audio(url);
    this.current = { audio, url };
    const done = () => {
      if (this.current?.audio !== audio) return; // stopped meanwhile
      URL.revokeObjectURL(url);
      this.#next();
    };
    audio.onended = done;
    audio.onerror = done;
    this.onChange(item.ownerId);
    audio.play().catch(done); // e.g. autoplay blocked: skip rather than stall the queue
  }
}
