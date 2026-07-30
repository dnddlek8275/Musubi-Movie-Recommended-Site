function formatMemory(value) {
  return value == null ? "—" : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })} MB`;
}

export default function ProcessTable({ processes = [] }) {
  return (
    <section className="process-section" aria-labelledby="process-title">
      <h3 id="process-title">GPU 프로세스</h3>
      {processes.length === 0 ? (
        <p className="empty-message">현재 GPU를 사용하는 프로세스가 없습니다.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th scope="col">PID</th><th scope="col">프로세스</th><th scope="col">실행 명령어</th><th scope="col">GPU 메모리</th></tr>
            </thead>
            <tbody>
              {processes.map((process) => (
                <tr key={process.pid}>
                  <td>{process.pid}</td>
                  <td>{process.name || "—"}</td>
                  <td className="command-cell" title={process.command || ""}>{process.command || "—"}</td>
                  <td>{formatMemory(process.used_memory_mb)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
