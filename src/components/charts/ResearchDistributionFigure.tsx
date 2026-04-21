import { useMemo, type ReactNode } from 'react';

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return NaN;
  if (sorted.length === 1) return sorted[0];
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] === undefined) return sorted[base];
  return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
}

function boxStats(values: number[]) {
  const sorted = [...values].filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (sorted.length === 0) {
    return { min: NaN, q1: NaN, med: NaN, q3: NaN, max: NaN, iqr: NaN, lower: NaN, upper: NaN, sorted };
  }
  const q1 = quantile(sorted, 0.25);
  const med = quantile(sorted, 0.5);
  const q3 = quantile(sorted, 0.75);
  const iqr = q3 - q1;
  const lowerFence = q1 - 1.5 * iqr;
  const upperFence = q3 + 1.5 * iqr;
  const lower = sorted.find((v) => v >= lowerFence) ?? sorted[0];
  const upper = [...sorted].reverse().find((v) => v <= upperFence) ?? sorted[sorted.length - 1];
  return { min: sorted[0], q1, med, q3, max: sorted[sorted.length - 1], iqr, lower, upper, sorted };
}

function jitter(seed: number, i: number): number {
  const x = Math.sin(seed * 12.9898 + i * 78.233) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
}

interface Props {
  figLabel: string;
  caption: string;
  valueAxisLabel: string;
  dcValues: number[];
  nonDcValues: number[];
  dcLabel?: string;
  nonDcLabel?: string;
}

export default function ResearchDistributionFigure({
  figLabel,
  caption,
  valueAxisLabel,
  dcValues,
  nonDcValues,
  dcLabel = 'DC-likely',
  nonDcLabel = 'Non-DC',
}: Props) {
  const plot = useMemo(() => {
    const dc = boxStats(dcValues);
    const nd = boxStats(nonDcValues);
    const allVals = [...dc.sorted, ...nd.sorted].filter((v) => Number.isFinite(v));
    if (allVals.length === 0) {
      return null;
    }
    const vmin = Math.min(...allVals);
    const vmax = Math.max(...allVals);
    const pad = (vmax - vmin) * 0.08 || 0.02;
    const y0 = vmin - pad;
    const y1 = vmax + pad;
    const yScale = (v: number) => 1 - (v - y0) / (y1 - y0);
    return { dc, nd, y0, y1, yScale };
  }, [dcValues, nonDcValues]);

  if (!plot) {
    return (
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 600 }}>{figLabel}</div>
        <p style={{ marginTop: 8 }}>No distribution data available.</p>
      </div>
    );
  }

  const { dc, nd, yScale } = plot;
  const w = 420;
  const h = 240;
  const padL = 48;
  const padR = 12;
  const padT = 28;
  const padB = 36;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;

  const groupCenters = [padL + innerW * 0.28, padL + innerW * 0.72];
  const boxW = 34;

  const drawGroup = (
    cx: number,
    stats: ReturnType<typeof boxStats>,
    values: number[],
    seed: number,
    color: string,
  ) => {
    if (!Number.isFinite(stats.q1)) return null;
    const yLower = padT + yScale(stats.lower) * innerH;
    const yQ1 = padT + yScale(stats.q1) * innerH;
    const yMed = padT + yScale(stats.med) * innerH;
    const yQ3 = padT + yScale(stats.q3) * innerH;
    const yUpper = padT + yScale(stats.upper) * innerH;
    const els: ReactNode[] = [];
    els.push(
      <line key="whisker" x1={cx} x2={cx} y1={yUpper} y2={yLower} stroke={color} strokeWidth={1.5} />,
    );
    els.push(
      <rect
        key="box"
        x={cx - boxW / 2}
        y={yQ3}
        width={boxW}
        height={Math.max(2, yQ1 - yQ3)}
        fill={color}
        fillOpacity={0.25}
        stroke={color}
        strokeWidth={1.5}
      />,
    );
    els.push(
      <line key="median" x1={cx - boxW / 2} x2={cx + boxW / 2} y1={yMed} y2={yMed} stroke={color} strokeWidth={2} />,
    );
    values.forEach((v, i) => {
      if (!Number.isFinite(v)) return;
      const y = padT + yScale(v) * innerH;
      const jx = cx + jitter(seed, i) * (boxW * 0.42);
      els.push(
        <circle key={`pt-${i}`} cx={jx} cy={y} r={3} fill={color} fillOpacity={0.55} stroke={color} strokeWidth={0.5} />,
      );
    });
    return <g>{els}</g>;
  };

  const yTicks = 4;
  const tickVals = Array.from({ length: yTicks + 1 }, (_, i) => plot.y0 + (i * (plot.y1 - plot.y0)) / yTicks);

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
      <div style={{ fontWeight: 600 }}>{figLabel}</div>
      <p style={{ marginTop: 6, fontSize: '0.9rem', opacity: 0.9 }}>{caption}</p>
      <p style={{ marginTop: 4, fontSize: '0.85rem' }}>
        <strong>n</strong>: {dcLabel} = {dcValues.length}, {nonDcLabel} = {nonDcValues.length}
      </p>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ marginTop: 8, maxWidth: 520 }}>
        <text x={padL} y={16} fontSize={11} fill="currentColor" opacity={0.8}>
          {valueAxisLabel}
        </text>
        {tickVals.map((tv, i) => {
          const y = padT + yScale(tv) * innerH;
          return (
            <g key={`tick-${i}`}>
              <line x1={padL - 4} x2={w - padR} y1={y} y2={y} stroke="var(--border)" strokeOpacity={0.35} />
              <text x={4} y={y + 4} fontSize={10} fill="currentColor" opacity={0.75}>
                {tv.toFixed(3)}
              </text>
            </g>
          );
        })}
        {drawGroup(groupCenters[0], dc, dcValues, 11, '#6366f1')}
        {drawGroup(groupCenters[1], nd, nonDcValues, 29, '#22c55e')}
        <text x={groupCenters[0]} y={h - 10} textAnchor="middle" fontSize={11} fill="currentColor">
          {dcLabel}
        </text>
        <text x={groupCenters[1]} y={h - 10} textAnchor="middle" fontSize={11} fill="currentColor">
          {nonDcLabel}
        </text>
      </svg>
      <p style={{ marginTop: 6, fontSize: '0.8rem', opacity: 0.8 }}>
        Box: quartiles; whiskers: Tukey fences; points: node-level values (jittered for visibility).
      </p>
    </div>
  );
}
