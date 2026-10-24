const GRADIENTS = [
  ["#ff9a8b", "#ff6a88"],
  ["#7f7fd5", "#86a8e7"],
  ["#43cea2", "#185a9d"],
  ["#f7971e", "#ffd200"],
  ["#c471f5", "#fa71cd"],
  ["#30cfd0", "#5b4fe0"],
  ["#f093fb", "#f5576c"],
  ["#5ee7df", "#b490ca"],
];

function hash(text) {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return h;
}

export function initials(name = "?") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

// Gradient initials avatar; `speaking` adds the pulsing voice ring.
export default function Avatar({ name, size = 40, speaking = false, status }) {
  const [from, to] = GRADIENTS[hash(name || "?") % GRADIENTS.length];
  return (
    <span
      className={`avatar${speaking ? " speaking" : ""}`}
      style={{ width: size, height: size, fontSize: size * 0.38, background: `linear-gradient(135deg, ${from}, ${to})` }}
      aria-hidden="true"
    >
      {initials(name)}
      {status && <span className={`avatar-dot ${status}`} />}
    </span>
  );
}

export function Equalizer() {
  return (
    <span className="eq" aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </span>
  );
}
