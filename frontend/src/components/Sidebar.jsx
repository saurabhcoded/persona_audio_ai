import Avatar from "./Avatar.jsx";
import Icon from "./Icon.jsx";

const STATUS_TEXT = { building: "Building…", failed: "Build failed" };

export default function Sidebar({ personas, selectedId, chats, apiStatus, onSelect, onNew, open, onClose }) {
  return (
    <aside className={`sidebar${open ? " open" : ""}`} aria-label="Personas">
      <div className="sidebar-head">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="sparkle" size={16} />
          </span>
          Persona Voice
        </div>
        <button type="button" className="icon-btn only-drawer" onClick={onClose} aria-label="Close">
          <Icon name="close" />
        </button>
      </div>

      <button type="button" className="new-btn" onClick={onNew}>
        <Icon name="plus" size={16} /> New persona
      </button>

      <ul className="persona-list">
        {personas.map((p) => {
          const last = (chats[p.id] || []).filter((m) => m.text).at(-1);
          const preview = STATUS_TEXT[p.status] ?? (last ? last.text.split("\n").at(-1) : p.tagline);
          return (
            <li key={p.id}>
              <button
                type="button"
                className={`persona-item${p.id === selectedId ? " active" : ""}`}
                onClick={() => onSelect(p.id)}
              >
                <Avatar name={p.name} size={40} status={p.status !== "ready" ? p.status : undefined} />
                <span className="persona-item-text">
                  <span className="persona-item-name">
                    {p.name}
                    {p.source === "demo" && <span className="tag">demo</span>}
                  </span>
                  <span className={`persona-item-preview ${p.status}`}>
                    {last?.role === "user" && p.status === "ready" ? "You: " : ""}
                    {preview}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="sidebar-foot">
        <span className={`status-dot ${apiStatus}`} /> API {apiStatus}
      </div>
    </aside>
  );
}
