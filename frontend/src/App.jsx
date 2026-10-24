import { useCallback, useEffect, useRef, useState } from "react";
import { apiDelete, apiGet, apiPostBlob, apiStream } from "./api.js";
import { AudioQueue, base64ToBlob } from "./audioQueue.js";
import NewPersona, { voiceLabel } from "./NewPersona.jsx";

const SELECTED_KEY = "persona-voice.selected";

const toLines = (text) =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

function readSelected() {
  try {
    return localStorage.getItem(SELECTED_KEY);
  } catch {
    return null;
  }
}

function saveSelected(id) {
  try {
    localStorage.setItem(SELECTED_KEY, id);
  } catch {
    /* storage unavailable: selection just isn't remembered */
  }
}

export default function App() {
  const [personas, setPersonas] = useState([]);
  const [selectedId, setSelectedId] = useState(readSelected);
  const [detail, setDetail] = useState(null);
  const [voices, setVoices] = useState([]);
  const [apiStatus, setApiStatus] = useState("checking");
  const [creating, setCreating] = useState(false);
  // per-persona chat history: { [personaId]: [{ id, role, text, ttsText?, clips?, streaming?, error? }] }
  // clips = audio Blobs per line, streamed with the reply, kept for replay
  const [chats, setChats] = useState({});
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [speakLive, setSpeakLive] = useState(true);
  const [showScript, setShowScript] = useState(false);
  const [showCard, setShowCard] = useState(false);
  const [speakingId, setSpeakingId] = useState(null);
  const abortRef = useRef(null);
  const playerRef = useRef(null);
  if (!playerRef.current) playerRef.current = new AudioQueue(setSpeakingId);
  const player = playerRef.current;
  const endRef = useRef(null);

  const persona = personas.find((p) => p.id === selectedId) ?? personas[0] ?? null;
  const messages = (persona && chats[persona.id]) || [];
  const anyBuilding = personas.some((p) => p.status === "building");

  const loadPersonas = useCallback(async () => {
    try {
      setPersonas(await apiGet("/personas"));
      setApiStatus("up");
    } catch {
      setApiStatus("down");
    }
  }, []);

  useEffect(() => {
    loadPersonas();
    apiGet("/voices")
      .then(setVoices)
      .catch(() => setVoices([]));
  }, [loadPersonas]);

  // Poll while a persona is building.
  useEffect(() => {
    if (!anyBuilding) return undefined;
    const t = setInterval(loadPersonas, 2000);
    return () => clearInterval(t);
  }, [anyBuilding, loadPersonas]);

  // Persona card for the selected persona, once it's ready.
  useEffect(() => {
    setDetail(null);
    if (!persona || persona.status !== "ready") return;
    apiGet(`/personas/${persona.id}`)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [persona?.id, persona?.status]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const select = (id) => {
    abortRef.current?.abort();
    player.stop();
    setSelectedId(id);
    saveSelected(id);
    setCreating(false);
  };

  const setMessages = (personaId, update) =>
    setChats((c) => ({ ...c, [personaId]: update(c[personaId] || []) }));

  const patch = (personaId, id, fields) =>
    setMessages(personaId, (ms) => ms.map((m) => (m.id === id ? { ...m, ...fields } : m)));

  const addClip = (personaId, id, blob) =>
    setMessages(personaId, (ms) => ms.map((m) => (m.id === id ? { ...m, clips: [...(m.clips || []), blob] } : m)));

  // Replay: reuse the clips streamed with the reply; otherwise synthesize the whole reply once.
  const speak = async (personaId, msg) => {
    player.stop();
    if (msg.clips?.length) {
      msg.clips.forEach((blob) => player.enqueue(blob, msg.id));
      return;
    }
    if (!msg.ttsText) return;
    setSpeakingId(msg.id);
    try {
      const blob = await apiPostBlob("/tts", { persona_id: personaId, text: msg.ttsText });
      addClip(personaId, msg.id, blob);
      player.enqueue(blob, msg.id);
    } catch (e) {
      setSpeakingId(null);
      patch(personaId, msg.id, { error: `Voice failed: ${e.message}` });
    }
  };

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || streaming || !persona || persona.status !== "ready") return;
    const pid = persona.id;

    const userMsg = { id: crypto.randomUUID(), role: "user", text };
    const replyId = crypto.randomUUID();
    const history = [...messages, userMsg]
      .filter((m) => m.text && !m.error)
      .map((m) => ({ role: m.role, text: m.text }));

    setMessages(pid, (ms) => [...ms, userMsg, { id: replyId, role: "persona", text: "", streaming: true }]);
    setInput("");
    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;
    player.stop();

    let reply = "";
    let textDone = false;
    try {
      await apiStream(
        "/chat/stream",
        { persona_id: pid, turns: history, speak: speakLive },
        {
          signal: controller.signal,
          onEvent: (event, data) => {
            if (event === "delta") {
              reply += data.text;
              patch(pid, replyId, { text: reply });
            } else if (event === "done") {
              textDone = true;
              patch(pid, replyId, { text: data.bubbles.join("\n"), ttsText: data.tts_text, streaming: false });
            } else if (event === "audio") {
              // Lines arrive in order, often while the text is still streaming: play right away.
              const blob = base64ToBlob(data.audio, data.format);
              addClip(pid, replyId, blob);
              player.enqueue(blob, replyId);
            } else if (event === "audio_error") {
              patch(pid, replyId, { voiceNote: "Voice skipped a line." });
            } else if (event === "error") {
              patch(pid, replyId, { streaming: false, error: data.message });
            }
          },
        },
      );
    } catch (err) {
      if (err.name !== "AbortError" || !textDone) {
        patch(pid, replyId, {
          streaming: false,
          error: err.name === "AbortError" ? "Stopped." : `Request failed: ${err.message}`,
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const remove = async () => {
    if (!persona || persona.source !== "chat") return;
    if (!window.confirm(`Delete ${persona.name}? This erases all of its stored data.`)) return;
    try {
      await apiDelete(`/personas/${persona.id}`);
      setChats(({ [persona.id]: _gone, ...rest }) => rest);
      await loadPersonas();
      setSelectedId(null);
    } catch (e) {
      window.alert(`Delete failed: ${e.message}`);
    }
  };

  const ready = persona?.status === "ready";

  return (
    <main className="chat-shell">
      <header className="chat-head">
        <div className="avatar" aria-hidden="true">
          {persona?.name?.[0]?.toUpperCase() ?? "?"}
        </div>
        <div className="who">
          <select
            className="persona-select"
            aria-label="Persona"
            value={persona?.id ?? ""}
            onChange={(e) => select(e.target.value)}
            disabled={!personas.length}
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.status === "building" ? " (building…)" : p.status === "failed" ? " (failed)" : ""}
              </option>
            ))}
          </select>
          <p className="muted tagline">{persona?.tagline ?? (apiStatus === "down" ? "Backend unreachable" : "")}</p>
        </div>
        <button type="button" className="secondary" onClick={() => setCreating(true)}>
          + New
        </button>
        <span className={`badge ${apiStatus}`}>{apiStatus}</span>
      </header>

      {creating ? (
        <NewPersona
          onCancel={() => setCreating(false)}
          onCreated={async (p) => {
            await loadPersonas();
            select(p.id);
          }}
        />
      ) : (
        <>
          <div className="toolbar">
            <label>
              <input type="checkbox" checked={speakLive} onChange={(e) => setSpeakLive(e.target.checked)} />
              Speak replies
            </label>
            <label>
              <input type="checkbox" checked={showScript} onChange={(e) => setShowScript(e.target.checked)} />
              Voice script
            </label>
            <label>
              <input type="checkbox" checked={showCard} onChange={(e) => setShowCard(e.target.checked)} />
              Persona card
            </label>
            {persona && (
              <span className="voice-name">
                Voice: {(() => {
                  const v = voices.find((x) => x.id === persona.voice_id);
                  return v ? voiceLabel(v) : "Fish default";
                })()}
              </span>
            )}
            {persona?.source === "chat" && (
              <button type="button" className="link danger" onClick={remove}>
                Delete persona
              </button>
            )}
          </div>

          {showCard && detail && (
            <section className="card-panel">
              <pre>{detail.card || "No card."}</pre>
              {detail.style && <pre className="muted">{detail.style}</pre>}
              {detail.report && (
                <p className="muted small">
                  Sanitized {detail.report.messages_in} messages: {detail.report.artifacts_dropped} media/system lines
                  dropped, {Object.values(detail.report.pii).reduce((a, b) => a + b, 0)} personal details redacted,{" "}
                  {detail.report.participants_pseudonymized} other people pseudonymized.
                </p>
              )}
            </section>
          )}

          {persona?.status === "building" && (
            <p className="banner">
              Building {persona.name} from the chat: reading style, emojis and real replies. This usually takes under a
              minute.
            </p>
          )}
          {persona?.status === "failed" && <p className="banner error">{persona.error}</p>}

          <section className="messages" aria-live="polite">
            {messages.length === 0 && ready && (
              <p className="empty muted">Say something to {persona.name}.</p>
            )}
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="row user">
                  <div className="bubble">{m.text}</div>
                </div>
              ) : (
                <div key={m.id} className="row persona">
                  {toLines(m.text).map((line, i) => (
                    <div key={i} className="bubble">
                      {line}
                    </div>
                  ))}
                  {m.streaming && !m.text && <div className="bubble typing">typing…</div>}
                  {m.error && <p className="error">{m.error}</p>}
                  {m.voiceNote && <p className="muted small">{m.voiceNote}</p>}
                  {!m.streaming && m.ttsText && (
                    <div className="reply-tools">
                      <button className="link" onClick={() => speak(persona.id, m)} disabled={speakingId === m.id}>
                        {speakingId === m.id ? "Speaking…" : "▶ Speak"}
                      </button>
                      {showScript && <code className="script">{m.ttsText}</code>}
                    </div>
                  )}
                </div>
              ),
            )}
            <div ref={endRef} />
          </section>

          <form className="composer" onSubmit={send}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={ready ? `Message ${persona.name}` : "Persona not ready yet"}
              disabled={!ready}
              autoFocus
            />
            {streaming ? (
              <button
                type="button"
                onClick={() => {
                  abortRef.current?.abort();
                  player.stop();
                }}
              >
                Stop
              </button>
            ) : (
              <button type="submit" disabled={!input.trim() || !ready}>
                Send
              </button>
            )}
          </form>
        </>
      )}
    </main>
  );
}
