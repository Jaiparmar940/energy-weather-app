import type { CorrelationRecord, ModelMetric, Node } from '../types';

export function nodeDcBucket(node: Node): 'dc' | 'nonDc' {
  if (node.classificationLabel) {
    const l = node.classificationLabel.toLowerCase();
    if (l === 'high_likelihood' || l === 'medium_likelihood') return 'dc';
    return 'nonDc';
  }
  return node.isDataCenterHeavy ? 'dc' : 'nonDc';
}

/** Node-level mean |weather correlation| — matches `build_hypothesis_exports.build_rq1_values`. */
export function rq1NodeMeanAbsCorrelations(
  correlations: CorrelationRecord[],
  nodes: Node[],
): { dc: number[]; nonDc: number[] } {
  const bucketById = new Map(nodes.map((n) => [n.id, nodeDcBucket(n)]));
  const sums = new Map<string, { sumAbs: number; count: number }>();
  for (const r of correlations) {
    const nid = r.nodeId;
    if (!nid) continue;
    const abs = Math.abs(r.correlation);
    if (!Number.isFinite(abs)) continue;
    const cur = sums.get(nid) ?? { sumAbs: 0, count: 0 };
    cur.sumAbs += abs;
    cur.count += 1;
    sums.set(nid, cur);
  }
  const dc: number[] = [];
  const nonDc: number[] = [];
  for (const [nodeId, { sumAbs, count }] of sums) {
    if (count === 0) continue;
    const bucket = bucketById.get(nodeId);
    if (!bucket) continue;
    const v = sumAbs / count;
    if (bucket === 'dc') dc.push(v);
    else nonDc.push(v);
  }
  return { dc, nonDc };
}

/**
 * Node-level mean weather-only nRMSE (fallback mean RMSE) — descriptive aggregation for charts.
 * Table 1 / `hypothesis_tests.json` may still use row-level observations; captions note the distinction.
 */
export function rq2NodeMeanWeatherOnlyError(metrics: ModelMetric[], nodes: Node[]): { dc: number[]; nonDc: number[] } {
  const bucketById = new Map(nodes.map((n) => [n.id, nodeDcBucket(n)]));
  const byNode = new Map<
    string,
    { nrmseSum: number; nrmseN: number; rmseSum: number; rmseN: number }
  >();

  for (const m of metrics) {
    if (m.modelType !== 'weatherOnly') continue;
    const nid = m.nodeId;
    if (!nid) continue;
    const row = byNode.get(nid) ?? { nrmseSum: 0, nrmseN: 0, rmseSum: 0, rmseN: 0 };
    if (m.nrmse != null && Number.isFinite(m.nrmse)) {
      row.nrmseSum += m.nrmse;
      row.nrmseN += 1;
    }
    if (Number.isFinite(m.rmse)) {
      row.rmseSum += m.rmse;
      row.rmseN += 1;
    }
    byNode.set(nid, row);
  }

  const dc: number[] = [];
  const nonDc: number[] = [];
  for (const [nodeId, row] of byNode) {
    const bucket = bucketById.get(nodeId);
    if (!bucket) continue;
    const v =
      row.nrmseN > 0 ? row.nrmseSum / row.nrmseN : row.rmseN > 0 ? row.rmseSum / row.rmseN : NaN;
    if (!Number.isFinite(v)) continue;
    if (bucket === 'dc') dc.push(v);
    else nonDc.push(v);
  }
  return { dc, nonDc };
}

export function rq2NodeMetricLabel(metrics: ModelMetric[]): 'nRMSE' | 'RMSE' {
  const wo = metrics.filter((m) => m.modelType === 'weatherOnly');
  return wo.some((m) => m.nrmse != null && Number.isFinite(m.nrmse)) ? 'nRMSE' : 'RMSE';
}
