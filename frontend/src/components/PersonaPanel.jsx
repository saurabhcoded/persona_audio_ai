import Avatar, { Equalizer } from "./Avatar.jsx";
import Icon from "./Icon.jsx";

// "- **Language:** writes in Hinglish" -> { title: "Language", body: "writes in Hinglish" }
function cardItems(card) {
  return card
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("-"))
    .map((l) => {
      const line = l.replace(/^-\s*/, "");
      const m = line.match(/^\*\*(.+?)\*\*:?\s*(.*)$/);
      const clean = (s) => s.replace(/\*\*/g, "").replace(/:$/, "");
      return m ? { title: clean(m[1]), body: clean(m[2]) } : { title: null, body: clean(line) };
    });
}

function Stat({ value, label }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export default function PersonaPanel({
  persona,
  detail,
  voice,
  speaking,
  previewing,
  onPreviewVoice,
  onDelete,
  open,
  onClose,
}) {
  if (!persona) return <aside className={`panel${open ? " open" : ""}`} />;
  const stats = detail?.stats;
  const report = detail?.report;
  const emojis = Object.entries(detail?.emoji_map ?? {});
  const items = detail?.card ? cardItems(detail.card) : [];
  const piiCount = report ? Object.values(report.pii).reduce((a, b) => a + b, 0) : 0;

  return (
    <aside className={`panel${open ? " open" : ""}`} aria-label={`About ${persona.name}`}>
      <button type="button" className="icon-btn panel-close only-drawer" onClick={onClose} aria-label="Close">
        <Icon name="close" />
      </button>

      <section className="hero">
        <Avatar name={persona.name} size={96} speaking={speaking} />
        <h2>{persona.name}</h2>
        <p className="hero-sub">
          {speaking ? (
            <span className="speaking-label">
              <Equalizer /> speaking
            </span>
          ) : (
            persona.tagline
          )}
        </p>
        <button
          type="button"
          className="voice-chip"
          onClick={() => voice && onPreviewVoice(voice.id)}
          disabled={!voice || previewing}
          title={voice ? "Preview this voice" : "Uses the Fish Audio default voice"}
        >
          <Icon name={previewing ? "volume" : "play"} size={14} />
          {voice ? `${voice.name} · ${voice.language}` : "Default voice"}
        </button>
      </section>

      {persona.status === "building" && (
        <section className="panel-section">
          <h3>Building persona</h3>
          <ul className="build-steps">
            <li>Cleaning personal details</li>
            <li>Measuring texting style</li>
            <li>Learning emoji → voice habits</li>
            <li>Indexing real replies</li>
          </ul>
        </section>
      )}

      {persona.status === "failed" && (
        <section className="panel-section">
          <p className="error">{persona.error}</p>
        </section>
      )}

      {stats && (
        <section className="panel-section">
          <h3>Texting style</h3>
          <div className="stats">
            <Stat value={stats.messages} label="messages" />
            <Stat value={stats.words_p50} label="words / msg" />
            <Stat value={stats.msgs_per_burst} label="msgs / turn" />
            <Stat value={`${stats.lowercase_start_pct}%`} label="lowercase" />
          </div>
        </section>
      )}

      {emojis.length > 0 && (
        <section className="panel-section">
          <h3>How their emojis sound</h3>
          <div className="emoji-chips">
            {emojis.map(([e, v]) => (
              <span key={e} className="emoji-chip" title={v.spoken_as ? `Alone: “${v.spoken_as}”` : undefined}>
                <span className="emoji-chip-emoji">{e}</span>
                {v.cue.replace(/\]\[/g, " · ").replace(/[[\]]/g, "")}
              </span>
            ))}
          </div>
        </section>
      )}

      {items.length > 0 && (
        <section className="panel-section">
          <h3>Personality</h3>
          <ul className="traits">
            {items.map((it, i) => (
              <li key={i}>
                {it.title && <strong>{it.title}</strong>}
                <span>{it.body}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report && (
        <section className="panel-section privacy">
          <h3>
            <Icon name="shield" size={15} /> Privacy
          </h3>
          <p>
            {report.messages_in} messages cleaned · {piiCount} personal details removed · {report.artifacts_dropped}{" "}
            media/system lines dropped
            {report.participants_pseudonymized ? ` · ${report.participants_pseudonymized} people pseudonymized` : ""}.
            The original chat file was never stored.
          </p>
        </section>
      )}

      {persona.source === "chat" && (
        <section className="panel-section">
          <button type="button" className="danger-btn" onClick={onDelete}>
            <Icon name="trash" size={15} /> Delete persona
          </button>
        </section>
      )}
    </aside>
  );
}
