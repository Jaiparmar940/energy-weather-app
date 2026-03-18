import type {
  Region,
  Node,
  CorrelationRecord,
  ModelMetric,
  CaseStudySeries,
  Period,
} from '../types';

export interface CorrelationFilters {
  regionIds?: string[];
  periods?: Period[];
  isDataCenterHeavyBucket?: Array<'dc' | 'nonDc' | 'all'>;
}

export interface ModelMetricFilters {
  regionIds?: string[];
  periods?: Period[];
  target?: 'load' | 'lmp';
}

const DATA_BASE = '/data';

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function getRegions(): Promise<Region[]> {
  return fetchJson<Region[]>(`${DATA_BASE}/regions.json`);
}

export function getNodes(): Promise<Node[]> {
  return fetchJson<Node[]>(`${DATA_BASE}/nodes.json`);
}

export async function getCorrelationSummaries(
  filters: CorrelationFilters = {},
): Promise<CorrelationRecord[]> {
  const all = await fetchJson<CorrelationRecord[]>(
    `${DATA_BASE}/correlations_by_region_period.json`,
  );

  return all.filter((record) => {
    if (filters.regionIds && !filters.regionIds.includes(record.regionId)) {
      return false;
    }
    if (filters.periods && !filters.periods.includes(record.period)) {
      return false;
    }
    if (
      filters.isDataCenterHeavyBucket &&
      !filters.isDataCenterHeavyBucket.includes(record.isDataCenterHeavyBucket)
    ) {
      return false;
    }
    return true;
  });
}

export async function getModelMetrics(
  filters: ModelMetricFilters = {},
): Promise<ModelMetric[]> {
  const all = await fetchJson<ModelMetric[]>(`${DATA_BASE}/model_performance.json`);

  return all.filter((metric) => {
    if (filters.regionIds && !filters.regionIds.includes(metric.regionId)) {
      return false;
    }
    if (filters.periods && !filters.periods.includes(metric.period)) {
      return false;
    }
    if (filters.target && metric.target !== filters.target) {
      return false;
    }
    return true;
  });
}

export function getCaseStudySeries(nodeId: string): Promise<CaseStudySeries[]> {
  return fetchJson<CaseStudySeries[]>(`${DATA_BASE}/case_studies/${nodeId}.json`);
}

