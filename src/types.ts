export type Period = 'preAI' | 'earlyAI' | 'recentAI';

export interface Region {
  id: string;
  name: string;
  iso: string;
  isDataCenterHeavy: boolean;
}

export interface Node {
  id: string;
  name: string;
  regionId: string;
  subregion?: string;
  lat: number;
  lon: number;
  isDataCenterHeavy: boolean;
}

export interface CorrelationRecord {
  nodeId?: string;
  regionId: string;
  period: Period;
  year?: number;
  variable: string;
  target: 'load' | 'lmp';
  correlation: number;
  pValue?: number;
  isDataCenterHeavyBucket: 'dc' | 'nonDc' | 'all';
}

export interface ModelMetric {
  regionId: string;
  period: Period;
  modelType: 'weatherOnly' | 'weatherPlusDc';
  target: 'load' | 'lmp';
  rmse: number;
  mae: number;
  r2: number;
}

export interface TimeSeriesPoint {
  timestamp: string;
  load: number;
  lmp?: number;
  temperature?: number;
  cdh?: number;
  hdh?: number;
}

export interface CaseStudySeries {
  nodeId: string;
  period: Period;
  points: TimeSeriesPoint[];
}

