const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, signal) {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(`서버 응답을 읽을 수 없습니다. (HTTP ${response.status})`);
  }
  if (!response.ok) {
    throw new Error(body.message || `API 요청에 실패했습니다. (HTTP ${response.status})`);
  }
  return body;
}

export function fetchGpuList(signal) {
  return request("/api/gpus", signal);
}

export function fetchGpuProcesses(gpuIndex, signal) {
  return request(`/api/gpus/${gpuIndex}/processes`, signal);
}
