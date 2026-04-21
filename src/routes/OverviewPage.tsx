import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import ResearchDistributionFigure from '../components/charts/ResearchDistributionFigure';
import MeanDifferenceCiFigure from '../components/charts/MeanDifferenceCiFigure';
import { getCorrelationSummaries, getHypothesisTests, getNodes, getRegions, getModelMetrics } from '../lib/dataClient';
import { rq1NodeMeanAbsCorrelations, rq2NodeMeanWeatherOnlyError, rq2NodeMetricLabel } from '../lib/researchPlotUtils';
import type { HypothesisMetricResult, ModelMetric } from '../types';

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

function formatNum(val: number | null | undefined, digits = 4): string {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  return val.toFixed(digits);
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

  const { data: hypothesisExport } = useQuery({
    queryKey: ['hypothesis-tests'],
    queryFn: getHypothesisTests,
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

  const rq1Result = hypothesisExport?.results.find((r) => r.metricKey === 'rq1_mean_abs_weather_correlation');
  const rq2Result = hypothesisExport?.results.find((r) => r.metricKey === 'rq2_weather_only_rmse');

  const rq1Dist = useMemo(() => {
    if (!correlations?.length || !nodes?.length) return { dc: [] as number[], nonDc: [] as number[] };
    return rq1NodeMeanAbsCorrelations(correlations, nodes);
  }, [correlations, nodes]);

  const rq2Dist = useMemo(() => {
    if (!modelMetrics?.length || !nodes?.length) return { dc: [] as number[], nonDc: [] as number[] };
    return rq2NodeMeanWeatherOnlyError(modelMetrics, nodes);
  }, [modelMetrics, nodes]);

  const rq2AxisLabel = modelMetrics?.length ? rq2NodeMetricLabel(modelMetrics) : 'nRMSE';

  const renderInferenceBadge = (result?: HypothesisMetricResult) => {
    if (!result) return <span>Loading…</span>;
    if (!result.inferenceEligible) {
      return <span style={{ color: '#c2410c', fontWeight: 600 }}>Descriptive only (insufficient sample)</span>;
    }
    if (result.pValue == null) {
      return <span style={{ color: '#a16207', fontWeight: 600 }}>Inference limited</span>;
    }
    if (result.significantAt05) {
      return <span style={{ color: '#166534', fontWeight: 600 }}>Significant at alpha=0.05</span>;
    }
    return <span style={{ color: '#334155', fontWeight: 600 }}>Not significant at alpha=0.05</span>;
  };

  return (
    <div>
      <h2>Overview</h2>
      <p>
        This dashboard explores how strongly weather explains grid demand and pricing, and how that
        relationship appears to change in regions with heavy data center presence.
      </p>
      <section>
        <h3>RQ1 &amp; RQ2: distributions and uncertainty</h3>
        <p>
          Below: <strong>descriptive</strong> panels show per-node spread (box, optional density, jittered points;
          sample sizes annotated). <strong>Inferential</strong> panels plot the bootstrap 95% CI for the
          DC-minus-non-DC <em>mean</em> contrast from Table 1 (same gates as{' '}
          <code>hypothesis_tests.json</code>). They do not imply significance unless Table 1 does.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>
          <ResearchDistributionFigure
            figLabel="Fig A — RQ1 (descriptive)"
            caption="Node-level mean absolute weather correlation (all merged rows per node). Compare overlap and tails, not only bucket means."
            valueAxisLabel="Mean |ρ| per node"
            dcValues={rq1Dist.dc}
            nonDcValues={rq1Dist.nonDc}
          />
          <MeanDifferenceCiFigure
            figLabel="Fig B — RQ1 (inferential)"
            result={rq1Result}
            differenceDescription="mean |weather correlation| per node"
          />
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 16,
            alignItems: 'start',
            marginTop: 20,
          }}
        >
          <ResearchDistributionFigure
            figLabel="Fig C — RQ2 (descriptive)"
            caption={`Node-level mean weather-only ${rq2AxisLabel} (averaged across loaded evaluation rows per node). Uses normalized error when available.`}
            valueAxisLabel={`Mean ${rq2AxisLabel} per node`}
            dcValues={rq2Dist.dc}
            nonDcValues={rq2Dist.nonDc}
          />
          <MeanDifferenceCiFigure
            figLabel="Fig D — RQ2 (inferential)"
            result={rq2Result}
            differenceDescription={`group mean ${rq2AxisLabel} (weather-only rows; hypothesis script)`}
          />
        </div>
        <p style={{ marginTop: 16, fontSize: '0.9rem', opacity: 0.9 }}>
          Fig C aggregates one value per node for visualization; Fig D / Table 1 use row-level weather-only
          observations for the inferential contrast when sample gates pass.
        </p>
      </section>
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
        <h3>Table 1: Hypothesis tests (alpha = 0.05)</h3>
        <p>
          Inference is reported only if minimum sample-size gates are met. Otherwise rows are explicitly
          marked descriptive-only to avoid overclaiming.
        </p>
        <table>
          <thead>
            <tr>
              <th>Research question metric</th>
              <th>Mode</th>
              <th>N (DC / Non-DC)</th>
              <th>DC mean</th>
              <th>Non-DC mean</th>
              <th>Abs diff</th>
              <th>Rel diff %</th>
              <th>95% CI diff</th>
              <th>Effect size</th>
              <th>p-value</th>
              <th>Result label</th>
            </tr>
          </thead>
          <tbody>
            {[rq1Result, rq2Result].filter(Boolean).map((r) => (
              <tr key={r!.metricKey}>
                <td>{r!.metricLabel}</td>
                <td>{renderInferenceBadge(r!)}</td>
                <td>
                  {r!.nDc} / {r!.nNonDc}
                </td>
                <td>{formatNum(r!.dcMean)}</td>
                <td>{formatNum(r!.nonDcMean)}</td>
                <td>{formatNum(r!.absoluteDifference)}</td>
                <td>{formatNum(r!.relativeDifferencePct)}</td>
                <td>
                  {r!.diffCiLower == null || r!.diffCiUpper == null
                    ? '—'
                    : `[${formatNum(r!.diffCiLower)}, ${formatNum(r!.diffCiUpper)}]`}
                </td>
                <td>{formatNum(r!.standardizedEffectSize)}</td>
                <td>{formatNum(r!.pValue)}</td>
                <td>{r!.resultLabel}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {[rq1Result, rq2Result].filter(Boolean).map((r) => (
          <div key={`${r!.metricKey}-warnings`} style={{ marginTop: 10 }}>
            <strong>{r!.question} notes:</strong>
            <ul>
              {r!.warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
      <section>
        <h3>Interpretation notes</h3>
        <ul>
          <li>
            RQ1 is shown as a node-level descriptive contrast in correlation magnitude; sample-size gates in
            Table 1 control when inferential summaries (CI, permutation p) are reported.
          </li>
          <li>
            RQ2 compares weather-only predictive error between DC-likely and non-DC groups using nRMSE when
            available, improving cross-node scale comparability.
          </li>
          <li>
            Confidence intervals and effect sizes are reported alongside p-values to prevent over-reliance on
            significance alone.
          </li>
        </ul>
      </section>
    </div>
  );
}

