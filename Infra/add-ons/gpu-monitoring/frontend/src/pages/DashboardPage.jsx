import { useCallback, useEffect, useRef, useState } from "react";
import { fetchGpuList } from "../api/gpuApi";
import GpuCard from "../components/GpuCard";
import StatusBadge from "../components/StatusBadge";

const intervals = [1000, 2000, 5000, 10000];

function LoadingCards() {
  return <div className="gpu-grid" aria-label="GPU 정보를 불러오는 중">{[0, 1].map((item) => <div className="gpu-card skeleton" key={item}><div /><div /><div /><div /></div>)}</div>;
}

export default function DashboardPage() {
  const [gpus, setGpus] = useState([]);
  const [histories, setHistories] = useState({});
  const [connected, setConnected] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshMs, setRefreshMs] = useState(2000);
  const activeController = useRef(null);

  const loadGpus = useCallback(async () => {
    activeController.current?.abort();
    const controller = new AbortController();
    activeController.current = controller;
    try {
      const response = await fetchGpuList(controller.signal);
      setConnected(true);
      setError("");
      setUnavailable(response.state === "unavailable");
      if (response.state === "success") {
        setGpus(response.data);
        const sampledAt = new Date(response.timestamp);
        const time = sampledAt.toLocaleTimeString("ko-KR", { hour12: false });
        setHistories((previous) => {
          const next = { ...previous };
          response.data.forEach((gpu) => {
            const point = { time, gpu: gpu.gpu_usage_percent, memory: gpu.memory_usage_percent, temperature: gpu.temperature_celsius, power: gpu.power_usage_watts };
            next[gpu.index] = [...(previous[gpu.index] || []), point].slice(-60);
          });
          return next;
        });
      }
      setLastUpdated(sampledAtOrNow(response.timestamp));
    } catch (requestError) {
      if (requestError.name !== "AbortError") {
        setConnected(false);
        setError(requestError.message || "GPU 서버에 연결할 수 없습니다.");
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGpus();
    return () => activeController.current?.abort();
  }, [loadGpus]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const intervalId = window.setInterval(loadGpus, refreshMs);
    return () => window.clearInterval(intervalId);
  }, [autoRefresh, refreshMs, loadGpus]);

  const status = connected
    ? unavailable ? { level: "warning", label: "GPU 미지원" } : { level: "normal", label: "서버 연결됨" }
    : { level: "danger", label: "연결 끊김" };

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div><p className="eyebrow">NVIDIA SERVER TELEMETRY</p><h1>GPU Monitoring Dashboard</h1><p className="subtitle">서버의 GPU 부하와 리소스를 실시간으로 확인합니다.</p></div>
        <div className="connection-panel"><StatusBadge level={status.level}>{status.label}</StatusBadge><span>마지막 업데이트 <strong>{lastUpdated ? lastUpdated.toLocaleTimeString("ko-KR") : "—"}</strong></span></div>
      </header>
      <section className="toolbar" aria-label="새로고침 설정">
        <button className={`toggle-button ${autoRefresh ? "active" : ""}`} type="button" aria-pressed={autoRefresh} onClick={() => setAutoRefresh((value) => !value)}>자동 새로고침 {autoRefresh ? "ON" : "OFF"}</button>
        <label>주기<select value={refreshMs} onChange={(event) => setRefreshMs(Number(event.target.value))} disabled={!autoRefresh}>{intervals.map((value) => <option value={value} key={value}>{value / 1000}초</option>)}</select></label>
        <button className="refresh-button" type="button" onClick={loadGpus} aria-label="GPU 상태 지금 새로고침">지금 새로고침</button>
      </section>
      {error && <div className="alert error-alert" role="alert"><strong>API 연결 오류</strong><span>{error} 기존 데이터가 있으면 계속 표시합니다.</span></div>}
      {unavailable && <div className="alert warning-alert" role="status"><strong>NVIDIA GPU를 사용할 수 없습니다.</strong><span>백엔드에서 <code>USE_MOCK_GPU_DATA=true</code>로 목업 모드를 켤 수 있습니다.</span></div>}
      {loading && gpus.length === 0 ? <LoadingCards /> : gpus.length > 0 ? (
        <section className="gpu-grid" aria-label="GPU 상태 목록">{gpus.map((gpu) => <GpuCard key={gpu.uuid || gpu.index} gpu={gpu} history={histories[gpu.index] || []} />)}</section>
      ) : !unavailable && !error ? <p className="empty-state">감지된 GPU가 없습니다.</p> : null}
    </main>
  );
}

function sampledAtOrNow(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? new Date() : date;
}
