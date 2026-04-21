import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { getModelMetrics } from '../lib/dataClient';
import ModelRmseBarChart from '../components/charts/ModelRmseBarChart';

export default function ModelsPage() {
  const [target, setTarget] = useState<'all' | 'lmp' | 'load'>('all');
  const [bucket, setBucket] = useState<'all' | 'dc' | 'nonDc'>('all');
  const [modelName, setModelName] = useState<string>('all');

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['model-metrics'],
    queryFn: () => getModelMetrics(),
  });

  const modelNames = useMemo(() => {
    if (!metrics) return [];
    return Array.from(new Set(metrics.map((m) => m.modelName).filter(Boolean))).sort() as string[];
  }, [metrics]);

  const filteredMetrics = useMemo(() => {
    if (!metrics) return [];
    return metrics.filter((m) => {
      if (target !== 'all' && m.target !== target) return false;
      if (bucket !== 'all' && (m.isDataCenterHeavyBucket ?? 'all') !== bucket) return false;
      if (modelName !== 'all' && (m.modelName ?? 'unknown') !== modelName) return false;
      return true;
    });
  }, [metrics, target, bucket, modelName]);

  return (
    <div>
      <h2>Prediction Model Accuracy</h2>
      <p>
        Compare how well weather-based models explain demand and pricing in data-center-heavy versus
        non–data-center-heavy regions, and how much additional signal comes from data-center proxies.
      </p>
      {isLoading || !metrics ? (
        <p>Loading model performance metrics…</p>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
            <label>
              Target{' '}
              <select value={target} onChange={(e) => setTarget(e.target.value as 'all' | 'lmp' | 'load')}>
                <option value="all">All</option>
                <option value="lmp">LMP</option>
                <option value="load">Load</option>
              </select>
            </label>
            <label>
              Region bucket{' '}
              <select value={bucket} onChange={(e) => setBucket(e.target.value as 'all' | 'dc' | 'nonDc')}>
                <option value="all">All</option>
                <option value="dc">DC-heavy</option>
                <option value="nonDc">Non-DC-heavy</option>
              </select>
            </label>
            <label>
              Model name{' '}
              <select value={modelName} onChange={(e) => setModelName(e.target.value)}>
                <option value="all">All</option>
                {modelNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ModelRmseBarChart metrics={filteredMetrics} />
          <table>
          <thead>
            <tr>
              <th>Region</th>
              <th>Bucket</th>
              <th>Period</th>
              <th>Target</th>
              <th>Model Type</th>
              <th>Model Name</th>
              <th>Samples</th>
              <th>RMSE</th>
              <th>MAE</th>
              <th>R²</th>
            </tr>
          </thead>
          <tbody>
            {filteredMetrics.slice(0, 80).map((m, idx) => (
              <tr key={idx}>
                <td>{m.regionId}</td>
                <td>{m.isDataCenterHeavyBucket ?? 'all'}</td>
                <td>{m.period}</td>
                <td>{m.target}</td>
                <td>{m.modelType}</td>
                <td>{m.modelName ?? 'unknown'}</td>
                <td>{m.nSamples ?? '-'}</td>
                <td>{m.rmse.toFixed(3)}</td>
                <td>{m.mae.toFixed(3)}</td>
                <td>{m.r2.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </>
      )}
    </div>
  );
}

