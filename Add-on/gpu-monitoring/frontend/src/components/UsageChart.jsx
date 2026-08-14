import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const lines = [
  { key: "gpu", name: "GPU", color: "#55d6be", unit: "%", yAxisId: "percent" },
  { key: "memory", name: "VRAM", color: "#60a5fa", unit: "%", yAxisId: "percent" },
  { key: "temperature", name: "온도", color: "#fbbf24", unit: "°C", yAxisId: "percent" },
  { key: "power", name: "전력", color: "#c084fc", unit: "W", yAxisId: "power" },
];

export default function UsageChart({ data }) {
  return (
    <section className="chart-section" aria-label="최근 GPU 상태 그래프">
      <div className="chart-header">
        <h3>최근 활동</h3>
        <span>최근 {data.length}/60회</span>
      </div>
      <div className="chart-legend" aria-hidden="true">
        {lines.map((line) => <span key={line.key}><i style={{ background: line.color }} />{line.name}</span>)}
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -26, bottom: 0 }}>
            <CartesianGrid stroke="#203047" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: "#8291a7", fontSize: 10 }} minTickGap={28} />
            <YAxis yAxisId="percent" domain={[0, 100]} tick={{ fill: "#8291a7", fontSize: 10 }} />
            <YAxis yAxisId="power" orientation="right" hide domain={[0, "auto"]} />
            <Tooltip contentStyle={{ background: "#101c2d", border: "1px solid #2a3c54", borderRadius: 8 }} />
            {lines.map((line) => (
              <Line key={line.key} type="monotone" dataKey={line.key} name={`${line.name} (${line.unit})`} yAxisId={line.yAxisId} stroke={line.color} dot={false} strokeWidth={2} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
