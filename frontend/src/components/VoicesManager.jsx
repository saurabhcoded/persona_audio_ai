import { useState } from "react";
import { apiDelete, apiSendJson } from "../api.js";
import Icon from "./Icon.jsx";

// Manage the voice catalog: preview, add a Fish Audio voice by ID, remove custom voices.
export default function VoicesManager({ voices, previewingId, onPreview, onChanged, onClose }) {
  const [voiceId, setVoiceId] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [added, setAdded] = useState(null);

  const add = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setAdded(null);
    try {
      const v = await apiSendJson("POST", "/voices", { voice_id: voiceId.trim(), name: name.trim() || null });
      setAdded(v);
      setVoiceId("");
      setName("");
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (v) => {
    if (!window.confirm(`Remove ${v.name}? Personas using it keep speaking with it until you change their voice.`))
      return;
    try {
      await apiDelete(`/voices/${v.id}`);
    } finally {
      onChanged();
    }
  };

  return (
    <div className="new-persona voices-manager">
      <div className="new-persona-intro">
        <h2>Voices</h2>
        <p>Every voice here can be picked when creating a persona or from a persona's profile.</p>
      </div>

      <form className="step add-voice" onSubmit={add}>
        <span className="step-n">
          <Icon name="plus" size={16} />
        </span>
        <div className="step-body">
          <h3>Add a Fish Audio voice</h3>
          <p className="hint">
            Open a voice on fish.audio and copy the 32-character ID from its URL (fish.audio/m/<b>voice-id</b>). Name
            and language are filled in from Fish Audio.
          </p>
          <div className="voice-row">
            <input
              className="text-input mono"
              value={voiceId}
              onChange={(e) => setVoiceId(e.target.value)}
              placeholder="e.g. 4d7609058bd34213b1378b29efbde1f1"
              aria-label="Fish voice ID"
            />
            <input
              className="text-input name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name (optional)"
              maxLength={60}
              aria-label="Voice name"
            />
            <button type="submit" className="primary-btn" disabled={!voiceId.trim() || busy}>
              {busy ? "Checking…" : "Add voice"}
            </button>
          </div>
          {error && <p className="form-error">{error}</p>}
          {added && (
            <p className="note-chip">
              <Icon name="sparkle" size={13} /> Added {added.name} · {added.gender}, {added.language}
            </p>
          )}
        </div>
      </form>

      <ul className="voice-list">
        {voices.map((v) => (
          <li key={v.id} className="voice-item">
            <button
              type="button"
              className="icon-btn play-btn"
              onClick={() => onPreview(v.id)}
              disabled={previewingId === v.id}
              aria-label={`Preview ${v.name}`}
            >
              <Icon name={previewingId === v.id ? "volume" : "play"} size={15} />
            </button>
            <span className="voice-item-text">
              <span className="voice-item-name">
                {v.name}
                {v.custom && <span className="tag">custom</span>}
              </span>
              <span className="voice-item-meta">
                {v.gender} · {v.language} · {v.description}
              </span>
              <code className="voice-item-id">{v.id}</code>
            </span>
            {v.custom && (
              <button type="button" className="icon-btn small" onClick={() => remove(v)} aria-label={`Remove ${v.name}`}>
                <Icon name="trash" size={15} />
              </button>
            )}
          </li>
        ))}
      </ul>

      <div className="actions">
        <button type="button" className="ghost-btn" onClick={onClose}>
          Back to chat
        </button>
      </div>
    </div>
  );
}
