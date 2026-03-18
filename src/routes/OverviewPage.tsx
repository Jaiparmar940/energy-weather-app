import { useQuery } from '@tanstack/react-query';
import { getRegions, getModelMetrics } from '../lib/dataClient';
import type { ModelMetric } from '../types';

function summarizeModelGap(metrics: ModelMetric[]) {
  const grouped = new Map<string, { weatherOnly?: ModelMetric; weatherPlusDc?: ModelMetric }>();
  metrics.forEach((m) => {
    const key = `${m.regionId}-${m.period}-${m.target}`;
    const entry = grouped.get(key) ?? {};
    if (m.modelType === 'weatherOnly') entry.weatherOnly = m;
    if (m.modelType === 'weatherPlusDc') entry.weatherPlusDc = m;
    grouped.set(key, entry);
  });

  let count = 0;
  let totalImprovement = 0;
  grouped.forEach((entry) => {
    if (entry.weatherOnly && entry.weatherPlusDc) {
      totalImprovement += entry.weatherOnly.rmse - entry.weatherPlusDc.rmse;
      count += 1;
    }
  });

  return count > 0 ? totalImprovement / count : 0;
}

export default function OverviewPage() {
  const { data: regions } = useQuery({
    queryKey: ['regions'],
    queryFn: getRegions,
  });

  const { data: modelMetrics } = useQuery({
    queryKey: ['model-metrics-overview'],
    queryFn: () => getModelMetrics(),
  });

  const avgRmseImprovement = modelMetrics ? summarizeModelGap(modelMetrics) : 0;

  return (
    <div>
      <h2>Overview</h2>
      <p>
        This dashboard explores how strongly weather explains grid demand and pricing, and how that
        relationship appears to change in regions with heavy data center presence.
      </p>
      <section>
        <h3>Dataset coverage</h3>
        <p>
          Regions loaded:{' '}
          {regions ? (
            <strong>{regions.length}</strong>
          ) : (
            <span>Loading region metadata…</span>
          )}
        </p>
      </section>
      <section>
        <h3>High-level finding (model signal)</h3>
        {modelMetrics ? (
          <p>
            On average, adding data-center-aware features{' '}
            <strong>
              {avgRmseImprovement >= 0 ? 'reduces' : 'increases'} RMSE by{' '}
              {Math.abs(avgRmseImprovement).toFixed(3)}
            </strong>{' '}
            across loaded regions and periods.
          </p>
        ) : (
          <p>Loading model performance summaries…</p>
        )}
      </section>
    </div>
  );
}

