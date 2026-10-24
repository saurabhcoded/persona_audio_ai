import { useEffect, useRef, useState } from "react";
import { apiPostBlob, apiPostForm } from "./api.js";
import Icon from "./components/Icon.jsx";
import VoiceSelect from "./components/VoiceSelect.jsx";

export const PREVIEW_TEXT = "[happy] arre hello! [laughing] hahaha, kaisa hai tu?";

function Step({ n, title, done, children }) {
  return (
    <section className={`step${done ? " done" : ""}`}>
      <span className="step-n">{done ? "✓" : n}</span>
      <div className="step-body">
        <h3>{title}</h3>
        {children}
      </div>
    </section>
  );
}

export default function NewPersona({ voices, onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [participants, setParticipants] = useState(null);
  const [sender, setSender] = useState("");
  const [consent, setConsent] = useState(false);
  const [voiceId, setVoiceId] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    setVoiceId((current) => current || voices[0]?.id || "");
  }, [voices]);

  useEffect(() => () => audioRef.current?.pause(), []);

  const preview = async () => {
    audioRef.current?.pause();
    setPreviewing(true);
    setError(null);
    try {
      const blob = await apiPostBlob("/tts", { voice_id: voiceId, text: PREVIEW_TEXT });
      const audio = new Audio(URL.createObjectURL(blob));
      audioRef.current = audio;
      audio.onended = () => setPreviewing(false);
      await audio.play();
    } catch (err) {
      setError(`Preview failed: ${err.message}`);
      setPreviewing(false);
    }
  };

  const pickFile = async (e) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setParticipants(null);
    setSender("");
    setError(null);
    if (!f) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await apiPostForm("/personas/participants", form);
      setParticipants(res.participants);
      chooseSender(res.participants[0]?.name ?? "");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const chooseSender = (value) => {
    setSender(value);
    setName((current) => (current.trim() ? current : value.split(" ")[0]));
  };

  const create = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("name", name.trim());
      form.append("sender", sender);
      form.append("consent", String(consent));
      if (voiceId) form.append("voice_id", voiceId);
      form.append("file", file);
      onCreated(await apiPostForm("/personas", form));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const ready = name.trim() && file && sender && consent && !busy;

  return (
    <form className="new-persona" onSubmit={create}>
      <div className="new-persona-intro">
        <h2>Bring someone's texting style to life</h2>
        <p>Upload a WhatsApp chat, pick who to learn from, and give them a voice.</p>
      </div>

      <Step n={1} title="Upload the WhatsApp chat" done={!!participants}>
        <label className={`dropzone${file ? " has-file" : ""}`}>
          <input type="file" accept=".txt,.zip" onChange={pickFile} />
          <Icon name="chat" size={22} />
          <span>{file ? file.name : "Choose a .txt or .zip export"}</span>
          <small>WhatsApp → open chat → ⋮ → More → Export chat → Without media</small>
        </label>
      </Step>

      <Step n={2} title="Who should the persona be?" done={!!sender && !!name.trim()}>
        {participants ? (
          <>
            <div className="choices">
              {participants.map((p) => (
                <label key={p.name} className={`choice-card${sender === p.name ? " selected" : ""}`}>
                  <input
                    type="radio"
                    name="sender"
                    value={p.name}
                    checked={sender === p.name}
                    onChange={() => chooseSender(p.name)}
                  />
                  <span className="choice-name">{p.name}</span>
                  <span className="choice-meta">{p.messages} messages</span>
                </label>
              ))}
            </div>
            <input
              className="text-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={60}
              placeholder="Persona name"
              aria-label="Persona name"
            />
          </>
        ) : (
          <p className="hint">Upload a chat first to see who's in it.</p>
        )}
      </Step>

      <Step n={3} title="Choose a voice" done={!!voiceId}>
        <div className="voice-row">
          <VoiceSelect voices={voices} value={voiceId} onChange={(v) => setVoiceId(v ?? "")} />
          <button type="button" className="ghost-btn" onClick={preview} disabled={!voiceId || previewing}>
            <Icon name={previewing ? "volume" : "play"} size={14} /> {previewing ? "Playing" : "Preview"}
          </button>
        </div>
        <p className="hint">For Hinglish chats the Hindi voices usually sound most natural.</p>
      </Step>

      <Step n={4} title="Consent" done={consent}>
        <label className="consent">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>
            I have this person's consent, or a clear right to use their chats (for example a family memorial).
            <small>
              Phone numbers, emails, ID/account numbers, links and other group members' names are removed before
              anything is stored. The uploaded file itself is never saved.
            </small>
          </span>
        </label>
      </Step>

      {error && <p className="form-error">{error}</p>}

      <div className="actions">
        <button type="button" className="ghost-btn" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="primary-btn" disabled={!ready}>
          {busy && participants ? "Creating…" : busy ? "Reading chat…" : "Create persona"}
        </button>
      </div>
    </form>
  );
}
