import StatusBadge from "./StatusBadge";

function statusFor(value, type) {
  if (value == null) return { level: "unknown", label: "정보 없음" };
  if (type === "temperature") {
    if (value >= 85) return { level: "danger", label: "위험" };
    if (value >= 75) return { level: "warning", label: "주의" };
    return { level: "normal", label: "정상" };
  }
  if (value >= 90) return { level: "danger", label: "높음" };
  if (value >= 70) return { level: "warning", label: "주의" };
  return { level: "normal", label: "정상" };
}

export default function ProgressBar({ label, value, type = "usage", unit = "%", max = 100 }) {
  const status = statusFor(value, type);
  const width = value == null ? 0 : Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="progress-group">
      <div className="progress-heading">
        <span>{label}</span>
        <span className="progress-value">{value == null ? "—" : `${Number(value).toFixed(0)}${unit}`}</span>
        <StatusBadge level={status.level}>{status.label}</StatusBadge>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin="0"
        aria-valuemax={max}
        aria-valuenow={value == null ? undefined : value}
        aria-valuetext={value == null ? "정보 없음" : `${value}${unit}, ${status.label}`}
      >
        <span className={`progress-fill fill-${status.level}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
