import { useEffect, useState } from "react";
import { apiSendJson } from "../api.js";
import Icon from "./Icon.jsx";

const VISIBLE = 8;

// Persona short forms ("r" → "are"): toggle, edit, add, re-detect from the chat; plus the
// options to expand them when speaking (default) and/or in the shown text.
export default function ShortformsEditor({ persona, detail, onSaved }) {
  const [forms, setForms] = useState(detail.shortforms);
  const [speech, setSpeech] = useState(detail.expand_shortforms_in_speech);
  const [text, setText] = useState(detail.expand_shortforms_in_text);
  const [newShort, setNewShort] = useState("");
  const [newFull, setNewFull] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [busy, setBusy] = useState(null); // "save" | "detect"
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setForms(detail.shortforms);
    setSpeech(detail.expand_shortforms_in_speech);
    setText(detail.expand_shortforms_in_text);
    setDirty(false);
  }, [detail]);

  const change = (fn) => {
    fn();
    setDirty(true);
  };
  const update = (i, fields) => change(() => setForms((fs) => fs.map((f, j) => (j === i ? { ...f, ...fields } : f))));

  const add = (e) => {
    e.preventDefault();
    const short = newShort.trim().toLowerCase();
    if (!short || !newFull.trim()) return;
    if (forms.some((f) => f.short === short)) {
      setError(`"${short}" is already in the list`);
      return;
    }
    change(() => setForms((fs) => [{ short, full: newFull.trim(), count: 0, example: "", enabled: true }, ...fs]));
    setNewShort("");
    setNewFull("");
    setError(null);
  };

  const save = async () => {
    setBusy("save");
    setError(null);
    try {
      onSaved(
        await apiSendJson("PUT", `/personas/${persona.id}/shortforms`, {
          shortforms: forms,
          expand_shortforms_in_speech: speech,
          expand_shortforms_in_text: text,
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const detect = async () => {
    setBusy("detect");
    setError(null);
    try {
      onSaved(await apiSendJson("POST", `/personas/${persona.id}/shortforms/detect`));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const shown = showAll ? forms : forms.slice(0, VISIBLE);

  return (
    <section className="panel-section shortforms">
      <h3>Short forms</h3>
      <div className="sf-options">
        <label className="switch">
          <input type="checkbox" checked={speech} onChange={(e) => change(() => setSpeech(e.target.checked))} />
          <span>Speak in full</span>
        </label>
        <label className="switch">
          <input type="checkbox" checked={text} onChange={(e) => change(() => setText(e.target.checked))} />
          <span>Show in full</span>
        </label>
      </div>

      {forms.length === 0 && (
        <p className="hint">
          No short forms yet.{persona.source === "chat" ? " Detect them from the chat, or add" : " Add"} one below.
        </p>
      )}

      <ul className="sf-list">
        {shown.map((f) => {
          const i = forms.indexOf(f);
          return (
            <li key={f.short} className={f.enabled ? "" : "off"} title={f.example ? `“${f.example}”` : undefined}>
              <input
                type="checkbox"
                checked={f.enabled}
                onChange={(e) => update(i, { enabled: e.target.checked })}
                aria-label={`Use ${f.short}`}
              />
              <code className="sf-short">{f.short}</code>
              <span className="sf-arrow">→</span>
              <input
                className="sf-full"
                value={f.full}
                onChange={(e) => update(i, { full: e.target.value })}
                aria-label={`Full form of ${f.short}`}
              />
              {f.count > 0 && <span className="sf-count">{f.count}×</span>}
              <button
                type="button"
                className="icon-btn small"
                onClick={() => change(() => setForms((fs) => fs.filter((_, j) => j !== i)))}
                aria-label={`Remove ${f.short}`}
              >
                <Icon name="close" size={13} />
              </button>
            </li>
          );
        })}
      </ul>
      {forms.length > VISIBLE && (
        <button type="button" className="link-btn" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show fewer" : `Show all ${forms.length}`}
        </button>
      )}

      <form className="sf-add" onSubmit={add}>
        <input value={newShort} onChange={(e) => setNewShort(e.target.value)} placeholder="tmrw" maxLength={15} />
        <span className="sf-arrow">→</span>
        <input value={newFull} onChange={(e) => setNewFull(e.target.value)} placeholder="tomorrow" maxLength={60} />
        <button type="submit" className="icon-btn small" disabled={!newShort.trim() || !newFull.trim()} aria-label="Add">
          <Icon name="plus" size={15} />
        </button>
      </form>

      {error && <p className="form-error">{error}</p>}

      <div className="sf-actions">
        {persona.source === "chat" && (
          <button type="button" className="ghost-btn small" onClick={detect} disabled={busy !== null}>
            <Icon name="sparkle" size={13} /> {busy === "detect" ? "Detecting…" : "Detect from chat"}
          </button>
        )}
        <button type="button" className="primary-btn small" onClick={save} disabled={!dirty || busy !== null}>
          {busy === "save" ? "Saving…" : dirty ? "Save" : "Saved"}
        </button>
      </div>
    </section>
  );
}
