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
  state?: string;
  county?: string;
  city?: string;
  lat: number;
  lon: number;
  isDataCenterHeavy: boolean;
  dataCenterLikelihoodScore?: number;
  confidenceScore?: number;
  classificationLabel?: 'high_likelihood' | 'medium_likelihood' | 'low_likelihood';
  reasonCodes?: string[];
  matchedRegion?: string;
  intermediateFeatures?: Record<string, unknown>;
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
  nodeId?: string;
  regionId: string;
  period: Period;
  isDataCenterHeavyBucket?: 'dc' | 'nonDc' | 'all';
  modelType: 'weatherOnly' | 'weatherPlusDc';
  modelName?: string;
  target: 'load' | 'lmp';
  split?: 'train' | 'test' | 'all';
  nSamples?: number;
  targetMean?: number;
  rmse: number;
  nrmse?: number | null;
  mae: number;
  r2: number;
}

export interface HypothesisMetricResult {
  metricKey: string;
  metricLabel: string;
  question: 'RQ1' | 'RQ2' | string;
  dcMean: number;
  nonDcMean: number;
  absoluteDifference: number;
  signedDifference: number;
  relativeDifferencePct?: number | null;
  dcMedian?: number | null;
  nonDcMedian?: number | null;
  dcStd?: number | null;
  nonDcStd?: number | null;
  dcIqr?: number | null;
  nonDcIqr?: number | null;
  nDc: number;
  nNonDc: number;
  diffCiLower?: number | null;
  diffCiUpper?: number | null;
  bootstrapIterations: number;
  standardizedEffectSize?: number | null;
  effectSizeLabel: string;
  pValue?: number | null;
  testType: string;
  permutationCount: number;
  inferenceEligible: boolean;
  testEligible: boolean;
  significantAt05?: boolean | null;
  resultLabel: string;
  warnings: string[];
}

export interface HypothesisTestsExport {
  metadata: Record<string, unknown>;
  results: HypothesisMetricResult[];
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

