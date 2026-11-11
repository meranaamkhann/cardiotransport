import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Bins, Curve, DecisionCurve, Measurement } from "../api/types";

export const PALETTE = ["#0f766e", "#c2410c", "#4f46e5", "#a16207", "#be185d", "#475569"];

const axis = { fontSize: 12, fill: "#55707a" };

export function TrendChart({ rows, unit }: { rows: Measurement[]; unit: string }) {
  const data = [...rows].reverse().map((m) => ({ t: new Date(m.measured_at).getTime(), value: m.value }));
  return (
    <div className="chart-box" role="img" aria-label={`Trend in ${unit}`}>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e3eaec" />
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tick={axis}
            tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })} />
          <YAxis tick={axis} domain={["auto", "auto"]} unit={` ${unit}`} width={72} />
          <Tooltip labelFormatter={(v) => new Date(v as number).toLocaleDateString()} formatter={(v) => [`${v} ${unit}`, "Value"]} />
          <Line type="monotone" dataKey="value" stroke={PALETTE[0]} strokeWidth={2.2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RocChart({ curves }: { curves: Record<string, Curve | null> }) {
  const names = Object.keys(curves).filter((n) => curves[n]);
  return (
    <div className="chart-box" role="img" aria-label="ROC curves">
      <ResponsiveContainer width="100%" height={340}>
        <LineChart margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="#e3eaec" />
          <XAxis type="number" dataKey="x" domain={[0, 1]} tick={axis} label={{ value: "False-positive rate", position: "insideBottom", offset: -12, fontSize: 12 }} />
          <YAxis type="number" domain={[0, 1]} tick={axis} label={{ value: "True-positive rate", angle: -90, position: "insideLeft", fontSize: 12 }} />
          <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(2) : v)} />
          <Legend verticalAlign="top" />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#8aa0a6" strokeDasharray="5 4" />
          {names.map((n, i) => (
            <Line key={n} name={n} data={curves[n]!.fpr.map((x, k) => ({ x, y: curves[n]!.tpr[k] }))} dataKey="y" stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={2} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CalibrationPlot({ curves }: { curves: Record<string, Bins | null> }) {
  const names = Object.keys(curves).filter((n) => curves[n]);
  return (
    <div className="chart-box" role="img" aria-label="Calibration curves">
      <ResponsiveContainer width="100%" height={340}>
        <LineChart margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="#e3eaec" />
          <XAxis type="number" dataKey="x" domain={[0, 1]} tick={axis} label={{ value: "Predicted probability", position: "insideBottom", offset: -12, fontSize: 12 }} />
          <YAxis type="number" domain={[0, 1]} tick={axis} label={{ value: "Observed proportion", angle: -90, position: "insideLeft", fontSize: 12 }} />
          <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(2) : v)} />
          <Legend verticalAlign="top" />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#8aa0a6" strokeDasharray="5 4" />
          {names.map((n, i) => (
            <Line key={n} name={n} data={curves[n]!.predicted.map((x, k) => ({ x, y: curves[n]!.observed[k] }))} dataKey="y" stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DecisionPlot({ curve }: { curve: DecisionCurve }) {
  const data = curve.thresholds.map((t, i) => ({ t, model: curve.model[i], adjusted: curve.prevalence_adjusted[i], all: curve.treat_all[i], none: curve.treat_none[i] }));
  return (
    <div className="chart-box" role="img" aria-label="Decision curve">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="#e3eaec" />
          <XAxis dataKey="t" tick={axis} label={{ value: "Threshold probability", position: "insideBottom", offset: -12, fontSize: 12 }} />
          <YAxis tick={axis} label={{ value: "Net benefit", angle: -90, position: "insideLeft", fontSize: 12 }} />
          <Tooltip />
          <Legend verticalAlign="top" />
          <Line name="Model" dataKey="model" stroke={PALETTE[0]} strokeWidth={2.2} dot={false} isAnimationActive={false} />
          <Line name="Model, prevalence-adjusted" dataKey="adjusted" stroke={PALETTE[2]} strokeWidth={2} strokeDasharray="6 3" dot={false} isAnimationActive={false} />
          <Line name="Treat all" dataKey="all" stroke={PALETTE[1]} dot={false} isAnimationActive={false} />
          <Line name="Treat none" dataKey="none" stroke="#475569" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GroupedBars({ data, keys, domain, label }: { data: Record<string, string | number | null>[]; keys: string[]; domain?: [number, number]; label: string }) {
  return (
    <div className="chart-box" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e3eaec" vertical={false} />
          <XAxis dataKey="name" tick={axis} />
          <YAxis tick={axis} domain={domain ?? [0, "auto"]} />
          <Tooltip />
          <Legend />
          {keys.map((k, i) => <Bar key={k} dataKey={k} name={k.replace(/_/g, " ")} fill={PALETTE[i % PALETTE.length]} radius={[3, 3, 0, 0]} isAnimationActive={false} />)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HorizontalBars({ rows, label }: { rows: { name: string; value: number }[]; label: string }) {
  return (
    <div className="chart-box" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 30 + 40)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 40 }}>
          <CartesianGrid stroke="#e3eaec" horizontal={false} />
          <XAxis type="number" tick={axis} />
          <YAxis type="category" dataKey="name" tick={axis} width={110} />
          <Tooltip />
          <Bar dataKey="value" fill={PALETTE[0]} radius={[0, 3, 3, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Heatmap({ rows, columns, values }: { rows: string[]; columns: string[]; values: Record<string, Record<string, number>> }) {
  const shade = (v: number) => `rgba(180, 35, 24, ${Math.min(1, v / 100) * 0.85 + (v > 0 ? 0.08 : 0)})`;
  return (
    <div className="scroll">
      <table className="heatmap">
        <thead><tr><th />{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th>{r}</th>
              {columns.map((c) => {
                const v = values[r]?.[c] ?? 0;
                return <td key={c} style={{ background: shade(v), color: v > 45 ? "#fff" : "#14313a" }}>{Math.round(v)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">Percentage of records missing, by cohort and predictor.</p>
    </div>
  );
}
