import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { CorrelationRecord } from '../../types';

interface Props {
  records: CorrelationRecord[];
}

export default function CorrelationBarChart({ records }: Props) {
  const top = [...records]
    .sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation))
    .slice(0, 12)
    .map((r) => ({
      // Keep axis labels short; full detail is in tooltip.
      label: `${r.nodeId ?? 'unknown'} • ${r.variable}`,
      nodeId: r.nodeId ?? 'unknown',
      regionId: r.regionId,
      period: r.period,
      variable: r.variable,
      target: r.target,
      value: r.correlation,
    }));

  const values = top.map((d) => d.value).filter((v) => Number.isFinite(v));
  const rawMin = values.length ? Math.min(...values) : -1;
  const rawMax = values.length ? Math.max(...values) : 1;
  const pad = 0.05;
  let yMin = rawMin - pad;
  let yMax = rawMax + pad;
  if (yMin > 0) yMin = 0;
  if (yMax < 0) yMax = 0;
  yMin = Math.max(-1, yMin);
  yMax = Math.min(1, yMax);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={top} margin={{ left: 16, right: 16, top: 8, bottom: 48 }}>
        <XAxis
          dataKey="label"
          type="category"
          interval={0}
          angle={-25}
          textAnchor="end"
          height={60}
          tick={{ fontSize: 11 }}
        />
        <YAxis
          type="number"
          domain={[yMin, yMax]}
          tickFormatter={(v) => Number(v).toFixed(2)}
          width={48}
        />
        <Tooltip
          formatter={(value, _name, props) => {
            const payload = props.payload as {
              nodeId: string;
              regionId: string;
              period: string;
              variable: string;
              target: string;
            };
            return [
              Number(value).toFixed(3),
              `corr (${payload.variable} → ${payload.target}) | node=${payload.nodeId} | region=${payload.regionId} | period=${payload.period}`,
            ];
          }}
        />
        <Bar dataKey="value" fill="#8884d8" name="Correlation" />
      </BarChart>
    </ResponsiveContainer>
  );
}

