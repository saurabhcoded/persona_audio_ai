import { useEffect, useRef, useState } from "react";
import { apiGet, apiPostBlob, apiPostForm } from "./api.js";

const PREVIEW_TEXT = "[happy] arre hello! [laughing] hahaha, kaisa hai tu?";

export const voiceLabel = (v) => `${v.name} · ${v.gender}, ${v.language}`;

export default function NewPersona({ onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [participants, setParticipants] = useState(null);
  const [sender, setSender] = useState("");
  const [consent, setConsent] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voiceId, setVoiceId] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const audioRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiGet("/voices")
      .then((list) => {
        setVoices(list);
        setVoiceId((current) => current || list[0]?.id || "");
      })
      .catch(() => setVoices([]));
    return () => audioRef.current?.pause();
  }, []);

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
      setSender(res.participants[0]?.name ?? "");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const chooseSender = (value) => {
    setSender(value);
    if (!name.trim()) setName(value.split(" ")[0]);
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
      <h2>New persona</h2>

      <label className="field">
        <span>WhatsApp chat export</span>
        <input type="file" accept=".txt,.zip" onChange={pickFile} />
        <small className="muted">
          In WhatsApp: open the chat → ⋮ → More → Export chat → Without media. Use the .txt (or .zip).
        </small>
      </label>

      {participants && (
        <fieldset className="field">
          <legend>Who should the persona be?</legend>
          {participants.map((p) => (
            <label key={p.name} className="choice">
              <input
                type="radio"
                name="sender"
                value={p.name}
                checked={sender === p.name}
                onChange={() => chooseSender(p.name)}
              />
              {p.name} <span className="muted">· {p.messages} messages</span>
            </label>
          ))}
        </fieldset>
      )}

      <label className="field">
        <span>Persona name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="e.g. Aman" />
      </label>

      <div className="field">
        <label htmlFor="voice">Voice</label>
        <div className="voice-row">
          <select id="voice" value={voiceId} onChange={(e) => setVoiceId(e.target.value)} disabled={!voices.length}>
            {["female", "male"].map((g) => (
              <optgroup key={g} label={g === "female" ? "Female" : "Male"}>
                {voices
                  .filter((v) => v.gender === g)
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} · {v.language} · {v.description}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
          <button type="button" className="secondary" onClick={preview} disabled={!voiceId || previewing}>
            {previewing ? "Playing…" : "▶ Preview"}
          </button>
        </div>
        <small className="muted">For Hinglish chats the Hindi voices usually sound most natural.</small>
      </div>

      <label className="choice consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          I have this person's consent, or a clear right to use their chats (for example a family memorial).
          <span className="muted">
            {" "}
            Phone numbers, emails, ID/account numbers, links and other group members' names are removed before
            anything is stored. The uploaded file itself is never saved.
          </span>
        </span>
      </label>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" disabled={!ready}>
          {busy && participants ? "Creating…" : busy ? "Reading chat…" : "Create persona"}
        </button>
      </div>
    </form>
  );
}
