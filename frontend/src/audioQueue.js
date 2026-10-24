const MIME = { mp3: "audio/mpeg", wav: "audio/wav", opus: "audio/ogg" };

// Smoothing (D-026). Fish clips start with ~50 ms and end with ~100–150 ms of silence, and
// their loudness differs by up to ~5 dB, so clips are trimmed, levelled and faded, then
// scheduled back to back on one Web Audio timeline with a short natural pause.
const PAUSE = 0.14; // seconds of breathing room between clips
const FADE = 0.008; // fade in/out, avoids clicks at clip edges
const SILENCE = 0.01; // amplitude treated as silence when trimming
const KEEP = 0.02; // seconds of silence kept at each trimmed edge
const TARGET_RMS = 0.18; // ≈ -15 dBFS, typical level of Fish voices
const MAX_GAIN = 3;
const PEAK = 0.97;

export function base64ToBlob(b64, format = "mp3") {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: MIME[format] ?? "audio/mpeg" });
}

// Trim leading/trailing silence, level to TARGET_RMS (without clipping), fade the edges.
export function smoothBuffer(ctx, buf) {
  const channels = Array.from({ length: buf.numberOfChannels }, (_, c) => buf.getChannelData(c));
  const n = buf.length;
  const loud = (i) => channels.some((d) => Math.abs(d[i]) > SILENCE);
  let start = 0;
  while (start < n && !loud(start)) start++;
  let end = n - 1;
  while (end > start && !loud(end)) end--;
  if (start >= end) return buf; // silent clip: leave as is

  const keep = Math.round(KEEP * buf.sampleRate);
  start = Math.max(0, start - keep);
  end = Math.min(n - 1, end + keep);
  const len = end - start + 1;

  let sum = 0;
  let peak = 0;
  for (const d of channels) {
    for (let i = start; i <= end; i++) {
      sum += d[i] * d[i];
      peak = Math.max(peak, Math.abs(d[i]));
    }
  }
  const rms = Math.sqrt(sum / (len * channels.length)) || TARGET_RMS;
  const gain = Math.min(MAX_GAIN, TARGET_RMS / rms, PEAK / (peak || 1));

  const out = ctx.createBuffer(channels.length, len, buf.sampleRate);
  const fade = Math.max(1, Math.round(FADE * buf.sampleRate));
  channels.forEach((d, c) => {
    const o = out.getChannelData(c);
    for (let i = 0; i < len; i++) {
      const edge = Math.min(1, i / fade, (len - 1 - i) / fade);
      o[i] = d[start + i] * gain * edge;
    }
  });
  return out;
}

// Plays audio clips smoothly, in the order they were queued. Clips are decoded as soon as
// they arrive (in parallel) but scheduled strictly in order.
// onChange(ownerId | null) reports which message is currently speaking.
export class AudioQueue {
  constructor(onChange) {
    this.onChange = onChange;
    this.ctx = null;
    this.chain = Promise.resolve();
    this.sources = new Set();
    this.nextTime = 0;
    this.generation = 0; // bumped by stop() so in-flight clips are dropped
    this.owner = null;
  }

  #context() {
    if (!this.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new Ctx();
    }
    // Created/resumed right after a user action (send, play), which browsers allow.
    if (this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  }

  enqueue(blob, ownerId) {
    const generation = this.generation;
    const ctx = this.#context();
    const ready = blob
      .arrayBuffer()
      .then((bytes) => ctx.decodeAudioData(bytes))
      .then((buf) => smoothBuffer(ctx, buf))
      .catch(() => null); // undecodable clip: skip it rather than stall the queue
    this.chain = this.chain.then(async () => {
      const buf = await ready;
      if (buf && generation === this.generation) this.#schedule(buf, ownerId);
    });
  }

  #schedule(buffer, ownerId) {
    const ctx = this.ctx;
    const now = ctx.currentTime;
    // Still playing: start after a short pause. Idle (or the clip arrived late): start now.
    const start = this.nextTime > now ? this.nextTime + PAUSE : now + 0.02;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start(start);
    this.nextTime = start + buffer.duration;
    this.sources.add(source);
    setTimeout(() => this.sources.has(source) && this.#set(ownerId), Math.max(0, (start - now) * 1000));
    source.onended = () => {
      this.sources.delete(source);
      if (this.sources.size === 0) this.#set(null);
    };
  }

  #set(owner) {
    if (owner !== this.owner) {
      this.owner = owner;
      this.onChange(owner);
    }
  }

  stop() {
    this.generation++;
    this.chain = Promise.resolve();
    for (const source of this.sources) {
      try {
        source.stop();
      } catch {
        /* not started yet */
      }
    }
    this.sources.clear();
    this.nextTime = 0;
    this.#set(null);
  }
}
