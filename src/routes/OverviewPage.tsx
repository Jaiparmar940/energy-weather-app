import { useQuery } from '@tanstack/react-query';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { getCorrelationSummaries, getNodes, getRegions, getModelMetrics } from '../lib/dataClient';
import type { CorrelationRecord, ModelMetric, Node } from '../types';

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

function isDcLikely(node?: Node): boolean {
  if (!node) return false;
  if (node.classificationLabel) {
    return node.classificationLabel === 'high_likelihood' || node.classificationLabel === 'medium_likelihood';
  }
  return node.isDataCenterHeavy;
}

function mean(vals: number[]): number {
  if (vals.length === 0) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function permutationPValue(sampleA: number[], sampleB: number[], iterations = 1500): number {
  if (sampleA.length === 0 || sampleB.length === 0) return 1;
  const observed = Math.abs(mean(sampleA) - mean(sampleB));
  const pooled = [...sampleA, ...sampleB];
  const nA = sampleA.length;
  let extreme = 0;
  for (let i = 0; i < iterations; i += 1) {
    // Fisher-Yates partial shuffle for the first nA elements.
    const arr = [...pooled];
    for (let j = arr.length - 1; j > 0; j -= 1) {
      const k = Math.floor(Math.random() * (j + 1));
      [arr[j], arr[k]] = [arr[k], arr[j]];
    }
    const groupA = arr.slice(0, nA);
    const groupB = arr.slice(nA);
    const diff = Math.abs(mean(groupA) - mean(groupB));
    if (diff >= observed) extreme += 1;
  }
  return (extreme + 1) / (iterations + 1);
}

interface HypothesisResult {
  metric: string;
  dcMean: number;
  nonDcMean: number;
  diff: number;
  pValue: number;
  significant: boolean;
  nDc: number;
  nNonDc: number;
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

  const { data: nodes } = useQuery({
    queryKey: ['nodes-overview'],
    queryFn: getNodes,
  });

  const { data: correlations } = useQuery({
    queryKey: ['correlations-overview'],
    queryFn: () => getCorrelationSummaries(),
  });

  const avgRmseImprovement = modelMetrics ? summarizeModelGap(modelMetrics) : 0;

  const rq1Result = (() => {
    if (!correlations || !nodes) return null;
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const byNode = new Map<string, number[]>();
    correlations.forEach((r: CorrelationRecord) => {
      if (!r.nodeId) return;
      const vals = byNode.get(r.nodeId) ?? [];
      vals.push(Math.abs(r.correlation));
      byNode.set(r.nodeId, vals);
    });
    const dcVals: number[] = [];
    const nonDcVals: number[] = [];
    byNode.forEach((vals, nodeId) => {
      const node = nodeById.get(nodeId);
      const nodeMean = mean(vals);
      if (isDcLikely(node)) dcVals.push(nodeMean);
      else nonDcVals.push(nodeMean);
    });
    const p = permutationPValue(dcVals, nonDcVals);
    const signedDiff = mean(dcVals) - mean(nonDcVals);
    return {
      metric: 'Mean |weather correlation| per node',
      dcMean: mean(dcVals),
      nonDcMean: mean(nonDcVals),
      diff: Math.abs(signedDiff),
      pValue: p,
      significant: p < 0.05,
      nDc: dcVals.length,
      nNonDc: nonDcVals.length,
    } as HypothesisResult;
  })();

  const rq2Result = (() => {
    if (!modelMetrics) return null;
    const weatherOnly = modelMetrics.filter((m) => m.modelType === 'weatherOnly');
    const dcVals = weatherOnly.filter((m) => (m.isDataCenterHeavyBucket ?? 'nonDc') === 'dc').map((m) => m.rmse);
    const nonDcVals = weatherOnly
      .filter((m) => (m.isDataCenterHeavyBucket ?? 'nonDc') === 'nonDc')
      .map((m) => m.rmse);
    const p = permutationPValue(dcVals, nonDcVals);
    return {
      metric: 'Weather-only RMSE',
      dcMean: mean(dcVals),
      nonDcMean: mean(nonDcVals),
      diff: mean(dcVals) - mean(nonDcVals),
      pValue: p,
      significant: p < 0.05,
      nDc: dcVals.length,
      nNonDc: nonDcVals.length,
    } as HypothesisResult;
  })();

  const rq1FigureData = [
    {
      label: 'RQ1: Mean |corr|',
      dc: rq1Result?.dcMean ?? 0,
      nonDc: rq1Result?.nonDcMean ?? 0,
    },
  ];
  const rq2FigureData = [
    {
      label: 'RQ2: Weather-only RMSE',
      dc: rq2Result?.dcMean ?? 0,
      nonDc: rq2Result?.nonDcMean ?? 0,
    },
  ];

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
      <section>
        <h3>Fig 1 and Fig 2: DC vs non-DC outcomes</h3>
        <p>
          Separate charts are shown so each metric keeps an appropriate y-scale.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <h4>Fig 1: RQ1 correlation-shift metric</h4>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rq1FigureData} margin={{ left: 16, right: 16 }}>
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="dc" name="DC-likely" fill="#8884d8" />
                <Bar dataKey="nonDc" name="Non-DC" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h4>Fig 2: RQ2 weather-only RMSE</h4>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rq2FigureData} margin={{ left: 16, right: 16 }}>
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="dc" name="DC-likely" fill="#8884d8" />
                <Bar dataKey="nonDc" name="Non-DC" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
      <section>
        <h3>Table 1: Hypothesis tests (alpha = 0.05)</h3>
        <p>
          Two-sided permutation tests evaluate whether DC-likely and non-DC groups differ for each
          question-level metric.
        </p>
        <table>
          <thead>
            <tr>
              <th>Research question metric</th>
              <th>DC mean</th>
              <th>Non-DC mean</th>
              <th>Absolute difference |DC - Non-DC|</th>
              <th>p-value</th>
              <th>Significant at 0.05?</th>
              <th>N (DC / Non-DC)</th>
            </tr>
          </thead>
          <tbody>
            {[rq1Result, rq2Result].filter(Boolean).map((r) => (
              <tr key={r!.metric}>
                <td>{r!.metric}</td>
                <td>{r!.dcMean.toFixed(4)}</td>
                <td>{r!.nonDcMean.toFixed(4)}</td>
                <td>{r!.diff.toFixed(4)}</td>
                <td>{r!.pValue.toFixed(4)}</td>
                <td>{r!.significant ? 'Yes' : 'No'}</td>
                <td>
                  {r!.nDc} / {r!.nNonDc}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h3>Interpretation notes</h3>
        <ul>
          <li>
            RQ1 asks whether weather-demand/price relationships shift by data-center intensity; Table 1
            tests whether average weather-correlation strength differs between DC-likely and non-DC nodes.
          </li>
          <li>
            RQ2 asks whether predictive accuracy differs by node type; Table 1 tests whether weather-only
            RMSE differs across DC-likely and non-DC groups.
          </li>
          <li>
            A statistically significant p-value (&lt; 0.05) indicates evidence that group means differ;
            non-significance indicates insufficient evidence under current sample and preprocessing choices.
          </li>
        </ul>
      </section>
    </div>
  );
}

