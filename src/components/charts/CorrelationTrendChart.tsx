import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { CorrelationRecord } from '../../types';

interface Props {
  records: CorrelationRecord[];
}

function keyFor(r: CorrelationRecord) {
  return `${r.nodeId ?? 'unknown'}|${r.variable}|${r.target}`;
}

export default function CorrelationTrendChart({ records }: Props) {
  const withYear = records.filter((r) => typeof r.year === 'number');
  if (withYear.length === 0) {
    return <p>No year-level correlation data yet. Rebuild exports with the new `year` field.</p>;
  }

  const seriesKeys = Array.from(new Set(withYear.map(keyFor))).slice(0, 8);
  const years = Array.from(new Set(withYear.map((r) => r.year as number))).sort((a, b) => a - b);

  const data = years.map((y) => {
    const row: Record<string, number | string> = { year: y };
    withYear
      .filter((r) => r.year === y && seriesKeys.includes(keyFor(r)))
      .forEach((r) => {
        row[keyFor(r)] = r.correlation;
      });
    return row;
  });

  const values: number[] = [];
  data.forEach((d) => {
    seriesKeys.forEach((k) => {
      const v = d[k];
      if (typeof v === 'number' && Number.isFinite(v)) values.push(v);
    });
  });
  const rawMin = values.length ? Math.min(...values) : -1;
  const rawMax = values.length ? Math.max(...values) : 1;
  const pad = 0.05;
  let yMin = rawMin - pad;
  let yMax = rawMax + pad;
  if (yMin > 0) yMin = 0;
  if (yMax < 0) yMax = 0;
  yMin = Math.max(-1, yMin);
  yMax = Math.min(1, yMax);

  const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7f50', '#8dd1e1', '#a4de6c', '#d0ed57', '#d885a3'];

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ left: 16, right: 16, top: 8, bottom: 12 }}>
        <XAxis dataKey="year" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11 }} />
        <YAxis
          type="number"
          domain={[yMin, yMax]}
          tickFormatter={(v) => Number(v).toFixed(2)}
          width={48}
        />
        <Tooltip
          formatter={(value, name) => [Number(value).toFixed(3), String(name).replace('|', ' • ')]}
          labelFormatter={(label) => `Year: ${label}`}
        />
        <Legend />
        {seriesKeys.map((k, i) => (
          <Line
            key={k}
            type="monotone"
            dataKey={k}
            dot={false}
            stroke={colors[i % colors.length]}
            connectNulls
            name={k.replace(/\|/g, ' • ')}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

