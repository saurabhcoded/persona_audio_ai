import { useCallback, useEffect, useRef, useState } from "react";
import { apiDelete, apiGet, apiPostBlob, apiSendJson, apiStream } from "./api.js";
import { AudioQueue, base64ToBlob } from "./audioQueue.js";
import Avatar, { Equalizer } from "./components/Avatar.jsx";
import Icon from "./components/Icon.jsx";
import PersonaPanel from "./components/PersonaPanel.jsx";
import RideCard from "./components/RideCard.jsx";
import Sidebar from "./components/Sidebar.jsx";
import VoicesManager from "./components/VoicesManager.jsx";
import NewPersona, { PREVIEW_TEXT } from "./NewPersona.jsx";

const SELECTED_KEY = "persona-voice.selected";
const SUGGESTIONS = ["Hey! kya chal raha hai? 👋", "Aaj ka din kaisa tha?", "Weekend ka kya plan hai?"];

const toLines = (text) =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

const clock = (ts) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

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
  const [places, setPlaces] = useState([]);
  // Draft ride per persona (from `ride_preview`), sent back until confirmed or replaced
  const [pendingRides, setPendingRides] = useState({});
  const [apiStatus, setApiStatus] = useState("checking");
  const [view, setView] = useState("chat"); // chat | new | voices
  const creating = view !== "chat";
  const [savingVoice, setSavingVoice] = useState(false);
  // per-persona chat history: { [personaId]: [{ id, role, text, at, ttsText?, clips?, rides?, choices?,
  //   notes?, streaming?, error? }] }  rides/choices/notes come from location assist
  // clips = audio Blobs per line, streamed with the reply, kept for replay
  const [chats, setChats] = useState({});
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [speakLive, setSpeakLive] = useState(true);
  const [showScript, setShowScript] = useState(false);
  const [speakingId, setSpeakingId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const abortRef = useRef(null);
  const playerRef = useRef(null);
  if (!playerRef.current) playerRef.current = new AudioQueue(setSpeakingId);
  const player = playerRef.current;
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const persona = personas.find((p) => p.id === selectedId) ?? personas[0] ?? null;
  const messages = (persona && chats[persona.id]) || [];
  const anyBuilding = personas.some((p) => p.status === "building");
  const voice = voices.find((v) => v.id === persona?.voice_id) ?? null;
  const personaSpeaking = messages.some((m) => m.id === speakingId);
  const typing = streaming && messages.at(-1)?.streaming;
  const ready = persona?.status === "ready";

  const loadPersonas = useCallback(async () => {
    try {
      setPersonas(await apiGet("/personas"));
      setApiStatus("up");
    } catch {
      setApiStatus("down");
    }
  }, []);

  const loadPlaces = useCallback(() => {
    apiGet("/places")
      .then(setPlaces)
      .catch(() => setPlaces([]));
  }, []);

  const loadVoices = useCallback(() => {
    apiGet("/voices")
      .then(setVoices)
      .catch(() => setVoices([]));
  }, []);

  useEffect(() => {
    loadPersonas();
    loadPlaces();
    loadVoices();
  }, [loadPersonas, loadPlaces, loadVoices]);

  // Poll while a persona is building.
  useEffect(() => {
    if (!anyBuilding) return undefined;
    const t = setInterval(loadPersonas, 2000);
    return () => clearInterval(t);
  }, [anyBuilding, loadPersonas]);

  // Profile details for the right panel, once the persona is ready.
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
    setView("chat");
    setSidebarOpen(false);
  };

  const setMessages = (personaId, update) =>
    setChats((c) => ({ ...c, [personaId]: update(c[personaId] || []) }));

  const patch = (personaId, id, fields) =>
    setMessages(personaId, (ms) => ms.map((m) => (m.id === id ? { ...m, ...fields } : m)));

  const append = (personaId, id, key, value) =>
    setMessages(personaId, (ms) => ms.map((m) => (m.id === id ? { ...m, [key]: [...(m[key] || []), value] } : m)));

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

  // Preview playback is owned by "preview:<voiceId>" so lists can show which one is playing.
  const previewVoice = async (voiceId) => {
    player.stop();
    const owner = `preview:${voiceId}`;
    setSpeakingId(owner);
    try {
      player.enqueue(await apiPostBlob("/tts", { voice_id: voiceId, text: PREVIEW_TEXT }), owner);
    } catch {
      setSpeakingId(null);
    }
  };

  const changeVoice = async (voiceId) => {
    if (!persona) return;
    setSavingVoice(true);
    try {
      await apiSendJson("PATCH", `/personas/${persona.id}/voice`, { voice_id: voiceId });
      await loadPersonas();
      if (voiceId) previewVoice(voiceId);
    } catch (e) {
      window.alert(`Couldn't change the voice: ${e.message}`);
    } finally {
      setSavingVoice(false);
    }
  };

  const send = async (e, preset) => {
    e?.preventDefault();
    const text = (preset ?? input).trim();
    if (!text || streaming || !persona || persona.status !== "ready") return;
    const pid = persona.id;

    const userMsg = { id: crypto.randomUUID(), role: "user", text, at: Date.now() };
    const replyId = crypto.randomUUID();
    const history = [...messages, userMsg]
      .filter((m) => m.text && !m.error)
      .map((m) => ({ role: m.role, text: m.text }));

    setMessages(pid, (ms) => [
      ...ms,
      userMsg,
      { id: replyId, role: "persona", text: "", streaming: true, at: Date.now() },
    ]);
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
        { persona_id: pid, turns: history, speak: speakLive, pending_ride: pendingRides[pid] ?? null },
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
            } else if (event === "ride_preview") {
              append(pid, replyId, "rides", data);
              setPendingRides((p) => ({ ...p, [pid]: data.draft }));
            } else if (event === "location") {
              append(pid, replyId, "rides", data);
              setPendingRides(({ [pid]: _done, ...rest }) => rest);
            } else if (event === "choices") {
              patch(pid, replyId, { choices: data.options });
            } else if (event === "saved_place") {
              append(pid, replyId, "notes", `Saved ${data.label}: ${data.name}`);
              loadPlaces();
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
      inputRef.current?.focus();
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    player.stop();
  };

  const forgetPlace = async (label) => {
    if (!window.confirm(`Forget your saved place "${label}"?`)) return;
    try {
      await apiDelete(`/places/${encodeURIComponent(label)}`);
    } finally {
      loadPlaces();
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
      setPanelOpen(false);
    } catch (e) {
      window.alert(`Delete failed: ${e.message}`);
    }
  };

  const statusLine = typing ? (
    <span className="typing-label">typing…</span>
  ) : personaSpeaking ? (
    <span className="speaking-label">
      <Equalizer /> speaking
    </span>
  ) : persona?.status === "building" ? (
    "building persona…"
  ) : voice ? (
    `voice: ${voice.name}`
  ) : (
    "online"
  );

  return (
    <div className={`app${creating || !persona ? " no-panel" : ""}`}>
      <Sidebar
        personas={personas}
        selectedId={persona?.id}
        chats={chats}
        places={places}
        onForgetPlace={forgetPlace}
        apiStatus={apiStatus}
        onSelect={select}
        onNew={() => {
          setView("new");
          setSidebarOpen(false);
        }}
        onVoices={() => {
          setView("voices");
          setSidebarOpen(false);
        }}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="chat">
        <header className="chat-head">
          <button type="button" className="icon-btn only-mobile" onClick={() => setSidebarOpen(true)} aria-label="Personas">
            <Icon name="menu" />
          </button>
          {persona && !creating && (
            <button type="button" className="chat-title" onClick={() => setPanelOpen(true)}>
              <Avatar name={persona.name} size={38} speaking={personaSpeaking} />
              <span>
                <span className="chat-name">{persona.name}</span>
                <span className="chat-status">{statusLine}</span>
              </span>
            </button>
          )}
          {creating && <span className="chat-name">{view === "new" ? "Create a persona" : "Voices"}</span>}
          <span className="spacer" />
          {!creating && (
            <>
              <button
                type="button"
                className={`icon-btn${speakLive ? " on" : ""}`}
                onClick={() => {
                  if (speakLive) player.stop();
                  setSpeakLive(!speakLive);
                }}
                aria-pressed={speakLive}
                title={speakLive ? "Voice on: replies are spoken as they stream" : "Voice off"}
              >
                <Icon name={speakLive ? "volume" : "volumeOff"} />
              </button>
              <button
                type="button"
                className={`icon-btn${showScript ? " on" : ""}`}
                onClick={() => setShowScript(!showScript)}
                aria-pressed={showScript}
                title="Show the voice script (cues sent to Fish Audio)"
              >
                <Icon name="code" />
              </button>
              <button
                type="button"
                className="icon-btn only-drawer-panel"
                onClick={() => setPanelOpen(true)}
                aria-label="Profile"
              >
                <Icon name="user" />
              </button>
            </>
          )}
        </header>

        {view === "voices" ? (
          <VoicesManager
            voices={voices}
            previewingId={speakingId?.startsWith("preview:") ? speakingId.slice(8) : null}
            onPreview={previewVoice}
            onChanged={loadVoices}
            onClose={() => setView("chat")}
          />
        ) : view === "new" ? (
          <NewPersona
            voices={voices}
            onCancel={() => setView("chat")}
            onCreated={async (p) => {
              await loadPersonas();
              select(p.id);
            }}
          />
        ) : (
          <>
            <section className="messages" aria-live="polite">
              {persona?.status === "building" && (
                <div className="notice">
                  <span className="spinner" /> Building {persona.name} from the chat — reading style, emojis and real
                  replies. Usually under a minute.
                </div>
              )}
              {persona?.status === "failed" && <div className="notice error">{persona.error}</div>}

              {messages.length === 0 && ready && (
                <div className="empty">
                  <Avatar name={persona.name} size={72} />
                  <h2>Say hi to {persona.name}</h2>
                  <p>Replies come in {persona.name}'s own style{speakLive ? " — and voice" : ""}.</p>
                  <div className="suggestions">
                    {SUGGESTIONS.map((s) => (
                      <button key={s} type="button" className="suggestion" onClick={() => send(null, s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="row user">
                    <div className="bubble">{m.text}</div>
                    <span className="meta">{clock(m.at)}</span>
                  </div>
                ) : (
                  <div key={m.id} className={`row persona${speakingId === m.id ? " is-speaking" : ""}`}>
                    {toLines(m.text).map((line, i) => (
                      <div key={i} className="bubble">
                        {line}
                      </div>
                    ))}
                    {m.streaming && !m.text && (
                      <div className="bubble typing" aria-label="typing">
                        <i />
                        <i />
                        <i />
                      </div>
                    )}
                    {m.rides?.map((ride, i) => (
                      <RideCard key={i} ride={ride} />
                    ))}
                    {m.notes?.map((note) => (
                      <span key={note} className="note-chip">
                        <Icon name="pin" size={13} /> {note}
                      </span>
                    ))}
                    {m.choices && m === messages.at(-1) && !streaming && (
                      <div className="choice-chips">
                        {m.choices.map((c) => (
                          <button key={c} type="button" className="suggestion" onClick={() => send(null, c)}>
                            {c}
                          </button>
                        ))}
                      </div>
                    )}
                    {m.error && <p className="msg-error">{m.error}</p>}
                    {!m.streaming && (m.text || m.rides) && (
                      <div className="meta">
                        {clock(m.at)}
                        {m.ttsText && (
                          <button
                            type="button"
                            className="replay"
                            onClick={() => (speakingId === m.id ? player.stop() : speak(persona.id, m))}
                          >
                            {speakingId === m.id ? (
                              <>
                                <Equalizer /> stop
                              </>
                            ) : (
                              <>
                                <Icon name="play" size={11} /> play
                              </>
                            )}
                          </button>
                        )}
                        {m.voiceNote && <span>· {m.voiceNote}</span>}
                      </div>
                    )}
                    {showScript && m.ttsText && <code className="script">{m.ttsText}</code>}
                  </div>
                ),
              )}
              <div ref={endRef} />
            </section>

            {pendingRides[persona?.id] && (
              <div className="pending-bar">
                <span className="pending-text">
                  <Icon name="map" size={15} />
                  <span>
                    Ride draft: <strong>{pendingRides[persona.id].origin_name}</strong> →{" "}
                    <strong>{pendingRides[persona.id].destination_name}</strong>
                  </span>
                </span>
                <button
                  type="button"
                  className="primary-btn small"
                  disabled={streaming}
                  onClick={() => send(null, "Confirm ✅")}
                >
                  Confirm ✅
                </button>
                <button
                  type="button"
                  className="ghost-btn small"
                  disabled={streaming}
                  onClick={() => setPendingRides(({ [persona.id]: _gone, ...rest }) => rest)}
                >
                  Cancel
                </button>
              </div>
            )}

            <form className="composer" onSubmit={send}>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={ready ? `Message ${persona.name}…` : "Persona not ready yet"}
                disabled={!ready}
                autoFocus
              />
              {streaming ? (
                <button type="button" className="send-btn stop" onClick={stop} aria-label="Stop">
                  <Icon name="stop" />
                </button>
              ) : (
                <button type="submit" className="send-btn" disabled={!input.trim() || !ready} aria-label="Send">
                  <Icon name="send" />
                </button>
              )}
            </form>
          </>
        )}
      </main>

      <PersonaPanel
        persona={creating ? null : persona}
        detail={detail}
        voice={voice}
        speaking={personaSpeaking}
        voices={voices}
        previewing={speakingId === `preview:${voice?.id}`}
        onPreviewVoice={previewVoice}
        onChangeVoice={changeVoice}
        savingVoice={savingVoice}
        onDetailChange={setDetail}
        onDelete={remove}
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
      />

      {(sidebarOpen || panelOpen) && (
        <div
          className="scrim"
          onClick={() => {
            setSidebarOpen(false);
            setPanelOpen(false);
          }}
        />
      )}
    </div>
  );
}
