const GROUPS = [
  ["female", "Female"],
  ["male", "Male"],
  ["other", "Other"],
];

export const voiceLabel = (v) => `${v.custom ? "★ " : ""}${v.name} · ${v.language}`;

// Voice dropdown grouped by gender; custom (user-added) voices are starred.
// `compact` drops the description (for narrow places like the profile panel).
export default function VoiceSelect({
  voices,
  value,
  onChange,
  allowDefault = false,
  compact = false,
  disabled,
  className = "text-input",
}) {
  return (
    <select
      className={className}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      disabled={disabled || !voices.length}
      aria-label="Voice"
    >
      {allowDefault && <option value="">Fish default voice</option>}
      {GROUPS.map(([g, label]) => {
        const group = voices.filter((v) => v.gender === g);
        return (
          group.length > 0 && (
            <optgroup key={g} label={label}>
              {group.map((v) => (
                <option key={v.id} value={v.id}>
                  {voiceLabel(v)}
                  {compact ? "" : ` · ${v.description}`}
                </option>
              ))}
            </optgroup>
          )
        );
      })}
    </select>
  );
}
