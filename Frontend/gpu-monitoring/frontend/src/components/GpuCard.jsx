import ProcessTable from "./ProcessTable";
import ProgressBar from "./ProgressBar";
import StatusBadge from "./StatusBadge";
import UsageChart from "./UsageChart";

const display = (value, unit, digits = 0) => value == null ? "—" : `${Number(value).toFixed(digits)} ${unit}`;

function overallStatus(gpu) {
  if (gpu.temperature_celsius >= 85) return { level: "danger", label: "위험" };
  if (gpu.gpu_usage_percent >= 90 || gpu.memory_usage_percent >= 90) return { level: "danger", label: "높음" };
  if (gpu.temperature_celsius >= 75 || gpu.gpu_usage_percent >= 70 || gpu.memory_usage_percent >= 70) {
    return { level: "warning", label: "주의" };
  }
  return { level: "normal", label: "정상" };
}

export default function GpuCard({ gpu, history }) {
  const status = overallStatus(gpu);
  return (
    <article className="gpu-card">
      <header className="gpu-card-header">
        <div><span className="eyebrow">GPU {gpu.index}</span><h2>{gpu.name || "알 수 없는 NVIDIA GPU"}</h2></div>
        <StatusBadge level={status.level}>{status.label}</StatusBadge>
      </header>
      <p className="gpu-uuid" title={gpu.uuid || ""}>{gpu.uuid || "UUID 정보 없음"}</p>
      <div className="progress-stack">
        <ProgressBar label="GPU 사용률" value={gpu.gpu_usage_percent} />
        <ProgressBar label="VRAM 사용률" value={gpu.memory_usage_percent} />
        <ProgressBar label="온도" value={gpu.temperature_celsius} type="temperature" unit="°C" />
      </div>
      <div className="metrics-grid">
        <div><span>VRAM</span><strong>{display(gpu.memory_used_mb, "MB", 0)}</strong><small>/ {display(gpu.memory_total_mb, "MB", 0)}</small></div>
        <div><span>전력</span><strong>{display(gpu.power_usage_watts, "W", 1)}</strong><small>/ {display(gpu.power_limit_watts, "W", 0)}</small></div>
        <div><span>팬 속도</span><strong>{display(gpu.fan_speed_percent, "%")}</strong></div>
        <div><span>그래픽 클럭</span><strong>{display(gpu.graphics_clock_mhz, "MHz")}</strong></div>
        <div><span>메모리 클럭</span><strong>{display(gpu.memory_clock_mhz, "MHz")}</strong></div>
        <div><span>드라이버</span><strong>{gpu.driver_version || "—"}</strong></div>
      </div>
      <UsageChart data={history} />
      <ProcessTable processes={gpu.processes} />
    </article>
  );
}
