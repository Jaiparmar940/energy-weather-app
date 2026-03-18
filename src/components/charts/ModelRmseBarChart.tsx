import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { ModelMetric } from '../../types';

interface Props {
  metrics: ModelMetric[];
}

export default function ModelRmseBarChart({ metrics }: Props) {
  const grouped = new Map<string, { label: string; weatherOnly?: number; weatherPlusDc?: number }>();

  metrics.forEach((m) => {
    const key = `${m.regionId}-${m.period}-${m.target}`;
    const label = `${m.regionId}-${m.period}-${m.target}`;
    const existing = grouped.get(key) ?? { label };
    if (m.modelType === 'weatherOnly') existing.weatherOnly = m.rmse;
    if (m.modelType === 'weatherPlusDc') existing.weatherPlusDc = m.rmse;
    grouped.set(key, existing);
  });

  const data = Array.from(grouped.values()).slice(0, 12);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ left: 16, right: 16 }}>
        <XAxis dataKey="label" tick={{ fontSize: 10 }} />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="weatherOnly" fill="#8884d8" name="Weather only RMSE" />
        <Bar dataKey="weatherPlusDc" fill="#82ca9d" name="Weather + DC RMSE" />
      </BarChart>
    </ResponsiveContainer>
  );
}

