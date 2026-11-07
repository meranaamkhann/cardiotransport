const PALETTE = ["#0f766e", "#c2410c", "#4f46e5", "#a16207"];

export function GroupedBars({ categories, series, max = 1, label }: {
  categories: string[]; series: { name: string; values: (number | null)[] }[]; max?: number; label: string;
}) {
  const width = 560, height = 240, left = 36, bottom = 34, top = 12;
  const plotH = height - bottom - top;
  const groupW = (width - left - 8) / categories.length;
  const barW = Math.min(34, (groupW - 16) / series.length);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        {ticks.map((t) => {
          const y = top + plotH - (t / max) * plotH;
          return (
            <g key={t}>
              <line x1={left} x2={width - 8} y1={y} y2={y} className="grid" />
              <text x={left - 6} y={y + 4} textAnchor="end" className="tick">{t.toFixed(2)}</text>
            </g>
          );
        })}
        {categories.map((c, ci) => {
          const x0 = left + ci * groupW + (groupW - barW * series.length) / 2;
          return (
            <g key={c}>
              {series.map((s, si) => {
                const v = s.values[ci];
                if (v === null || v === undefined) return null;
                const h = (v / max) * plotH;
                return (
                  <g key={s.name}>
                    <rect x={x0 + si * barW} y={top + plotH - h} width={barW - 3} height={h} rx={3} fill={PALETTE[si % PALETTE.length]} />
                    <text x={x0 + si * barW + (barW - 3) / 2} y={top + plotH - h - 4} textAnchor="middle" className="bar-value">{v.toFixed(2)}</text>
                  </g>
                );
              })}
              <text x={left + ci * groupW + groupW / 2} y={height - 12} textAnchor="middle" className="tick">{c}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="legend">
        {series.map((s, i) => (
          <span key={s.name}><i style={{ background: PALETTE[i % PALETTE.length] }} />{s.name}</span>
        ))}
      </figcaption>
    </figure>
  );
}

export function CalibrationChart({ curves, label }: {
  curves: Record<string, { predicted: number[]; observed: number[] }>; label: string;
}) {
  const size = 320, pad = 38;
  const span = size - pad - 12;
  const x = (v: number) => pad + v * span;
  const y = (v: number) => size - pad - v * span;
  const names = Object.keys(curves);
  return (
    <figure className="chart square">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} className="grid" />
            <line x1={x(t)} x2={x(t)} y1={y(0)} y2={y(1)} className="grid" />
            <text x={x(0) - 6} y={y(t) + 4} textAnchor="end" className="tick">{t}</text>
            <text x={x(t)} y={y(0) + 16} textAnchor="middle" className="tick">{t}</text>
          </g>
        ))}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} className="ideal" />
        {names.map((n, i) => {
          const c = curves[n];
          const points = c.predicted.map((p, k) => `${x(p)},${y(c.observed[k])}`).join(" ");
          return (
            <g key={n}>
              <polyline points={points} fill="none" stroke={PALETTE[i % PALETTE.length]} strokeWidth={2.2} />
              {c.predicted.map((p, k) => <circle key={k} cx={x(p)} cy={y(c.observed[k])} r={3.4} fill={PALETTE[i % PALETTE.length]} />)}
            </g>
          );
        })}
        <text x={size / 2} y={size - 4} textAnchor="middle" className="tick">Predicted score</text>
        <text x={10} y={size / 2} textAnchor="middle" className="tick" transform={`rotate(-90 10 ${size / 2})`}>Observed share with disease</text>
      </svg>
      <figcaption className="legend">
        {names.map((n, i) => <span key={n}><i style={{ background: PALETTE[i % PALETTE.length] }} />{n}</span>)}
        <span><i className="dash" />Perfect calibration</span>
      </figcaption>
    </figure>
  );
}

export function LineChart({ x, series, label, yLabel }: {
  x: string[]; series: { name: string; values: (number | null)[]; dashed?: boolean }[]; label: string; yLabel: string;
}) {
  const width = 560, height = 260, left = 52, bottom = 36, top = 12, right = 10;
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  const lo = Math.min(...all, 0), hi = Math.max(...all, 0.001);
  const pad = (hi - lo) * 0.08 || 0.01;
  const min = lo < 0 ? lo - pad : lo, max = hi + pad;
  const px = (i: number) => left + (x.length === 1 ? 0.5 : i / (x.length - 1)) * (width - left - right);
  const py = (v: number) => top + (1 - (v - min) / (max - min)) * (height - top - bottom);
  const step = Math.ceil(x.length / 8);
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        {[0, 1, 2, 3, 4].map((k) => {
          const v = min + ((max - min) * k) / 4;
          return (
            <g key={k}>
              <line x1={left} x2={width - right} y1={py(v)} y2={py(v)} className="grid" />
              <text x={left - 6} y={py(v) + 4} textAnchor="end" className="tick">{v.toFixed(2)}</text>
            </g>
          );
        })}
        {x.map((label2, i) => i % step === 0 && <text key={label2} x={px(i)} y={height - 16} textAnchor="middle" className="tick">{label2}</text>)}
        {series.map((s, si) => (
          <polyline key={s.name} fill="none" stroke={s.dashed ? "#7b8b90" : PALETTE[si % PALETTE.length]} strokeWidth={2.2}
            strokeDasharray={s.dashed ? "5 4" : undefined}
            points={s.values.map((v, i) => (v === null ? null : `${px(i)},${py(v)}`)).filter(Boolean).join(" ")} />
        ))}
        <text x={10} y={height / 2} textAnchor="middle" className="tick" transform={`rotate(-90 10 ${height / 2})`}>{yLabel}</text>
      </svg>
      <figcaption className="legend">
        {series.map((s, i) => <span key={s.name}><i style={{ background: s.dashed ? "#7b8b90" : PALETTE[i % PALETTE.length] }} />{s.name}</span>)}
      </figcaption>
    </figure>
  );
}
