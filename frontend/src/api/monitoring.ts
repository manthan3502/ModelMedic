import type { PerformanceResults, CalibrationResults, ErrorsResults } from './labeled'
export type Signal = {
  baseline_n: number; current_n: number; test: string | null; statistic: number | null
  raw_p: number | null; adjusted_p: number | null; status: string; bh_family_size?: number
  distance_name?: string; distance?: number | null; reason?: string | null; warnings?: string[]
}
export type Histogram = { bins: { lower: number | null; upper: number | null; baseline_count: number; current_count: number; baseline_share: number; current_share: number }[]; reason: string | null }
export type Category = { category: string; baseline_count: number; current_count: number; baseline_share: number; current_share: number; delta_pp: number }
export type Distribution = Signal & { plot?: Histogram; categories?: Category[]; baseline_min?: number | null; baseline_max?: number | null; outside_range_share?: number | null; new_categories?: string[]; disappeared_categories?: string[]; pooling_threshold?: number | null; pooling?: { id: string; label: string; members: string[] }[]; expected_counts?: number[][] }
export type Missingness = Signal & { baseline_missing_count: number; current_missing_count: number; baseline_missing_percent: number; current_missing_percent: number; delta_pp: number }
export type FeatureResult = { feature_id: string; name: string; type: string; distribution: Distribution; missingness: Missingness; reliance: { feature: string; mean: number; sd: number } | null; interpretation?: { measured: string; result: string; may_conclude: string; cannot_conclude: string; reliance: string } }
export type Validation = { errors: string[]; warnings: string[]; mode?: string; required_features?: string[]; ignored_extra_columns?: string[]; coercions?: { feature_id: string; name: string; observed_count: number; conversion: string }[]; new_categories?: { feature_id: string; name: string; categories: string[] }[] }
export type Run = {
  id: string; project_id: string; name: string; monitoring_date: string; notes: string | null
  created_at: string; analyzed_at: string | null; state: string; mode: string | null; row_count: number | null
  baseline_snapshot_id: string; methodology_version: string | null; code_version: string | null
  result_sha256: string | null; deletion_pending: boolean
  dataset: null | { id: string; status: string; validation_report: Validation | null; canonical_sha256: string | null; canonical_schema_version: string | null }
  job: null | { id: string; state: string; stage: string; error_message: string | null; started_at: string | null }
  summary: null | { counts: Record<string, number>; tested_features: number; median_confidence: number; performance?: Record<string, { value: number | null; reason: string | null }> }
}
export type MonitoringResults = {
  mode: 'A' | 'B'; limitation: string; frozen_statement: string; data_reference: string; model_reference: string
  performance?: PerformanceResults; calibration?: CalibrationResults; errors?: ErrorsResults
  baseline_snapshot_id: string; code_version: string; methodology_version: string; canonical_sha256: string
  bh_family_size: number; counts: Record<string, number>; tested_features: number; missingness_detected: number
  features: FeatureResult[]; validation: Validation; limitations: string[]
  predictions: Distribution & { class_order: string[]; interpretation: string; limitation: string }
  confidence: Signal & { baseline_mean: number; current_mean: number; baseline_median: number; current_median: number; plot: Histogram; limitation: string }
}
export const modeALimitation = 'Actual current predictive performance and calibration cannot be measured because ground-truth labels were not provided.'
export const frozenStatement = 'The established model and preprocessing are applied exactly as frozen. Nothing is retrained, refitted or updated from this file.'
