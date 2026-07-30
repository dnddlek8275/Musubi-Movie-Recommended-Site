export default function StatusBadge({ level = "normal", children }) {
  return <span className={`status-badge status-${level}`}>{children}</span>;
}
