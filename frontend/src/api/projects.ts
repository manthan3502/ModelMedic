export type FeatureType = 'numeric' | 'categorical'
export type Classifier = 'logistic_regression' | 'random_forest' | 'gradient_boosting'
export type Weighting = 'standard' | 'balanced'
export type ClassCount = { label: string; count: number; proportion: number }
export type Column = {
  feature_id: string; name: string; inferred_type: FeatureType; missing_count: number
  distinct_count: number; samples: string[]; flags: string[]; unsupported_reason: string | null
  allowed_types: FeatureType[]; target: { eligible: boolean; reasons: string[]; classes: ClassCount[]; class_balance_note?: string | null }
}
export type Configuration = {
  dataset_id: string; target_id: string; positive_class: string | null
  features: { feature_id: string; type: FeatureType }[]
  classifier: Classifier | null; weighting: Weighting | null
}
export type Metric = { value: number | null; reason: string | null }
export type BaselineResults = {
  metrics: { support: number; class_order: string[]; metrics: Record<string, Metric>; per_class: { class: string; support: number; precision: Metric; recall: Metric; f1: Metric }[]; confusion_matrix: number[][] }
  cv: Record<string, { values: (number | null)[]; mean?: number; sd?: number; min?: number; max?: number; reason: string | null }>
  calibration: { support: number; requested_bins: number; warning: string | null; classes: { class: string; positive_count: number; non_positive_count: number; reason: string | null; bins: { count: number; mean_probability: number; observed_rate: number }[] }[] }
  importance: { feature: string; mean: number; sd: number }[]
  development_count: number; heldout_count: number; class_order: string[]; class_counts: Record<string, number>; development_class_counts: Record<string, number>; heldout_class_counts: Record<string, number>; warnings: string[]
  manifest: Record<string, string | string[] | number | boolean | null | Record<string, string>>
  features: (Column & { frozen_type: FeatureType })[]
}
export type Project = {
  baseline?: null | { id: string; status: string; fingerprint: string; established_at: string | null; error_message: string | null; results: BaselineResults | null }

  id: string; name: string; description: string | null; state: string; deletion_pending: boolean
  created_at: string; updated_at: string; configuration: Partial<Configuration> & { encoded_columns?: number; class_order?: string[] }
  limits: { upload_max_bytes: number; max_rows: number; max_columns: number; max_features: number; max_categories: number; max_encoded_columns: number }
  dataset: null | { id: string; status: string; canonical_sha256: string | null; canonical_schema_version: string | null
    validation_report: null | { errors: string[]; warnings: string[] }
    profile: null | { row_count: number; column_count: number; duplicate_rows: number; columns: Column[]; preview: (string | null)[][] } }
  job: null | { id: string; state: string; stage: string; error_message: string | null; job_type?: string; started_at?: string | null }
  preprocessing: null | { steps: string[]; numeric: string; categorical: string; learning: string; frozen: string; fitted: boolean }
  confirmation: null | { ready: boolean; training_available: boolean; split: string; cv: string; seed: number; guardrail: string }
}
export const models: { value: Classifier; name: string; description: string; tradeoff: string }[] = [
  { value: 'logistic_regression', name: 'Logistic Regression', description: 'Simple probabilistic linear model.', tradeoff: 'Easy to inspect, but linear relationships can miss complex patterns.' },
  { value: 'random_forest', name: 'Random Forest', description: 'Non-linear ensemble of trees.', tradeoff: 'Captures interactions, but is less directly interpretable than a linear model.' },
  { value: 'gradient_boosting', name: 'Gradient Boosting', description: 'Sequential boosted trees.', tradeoff: 'Captures non-linear patterns, but fitting can take longer.' },
]
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init)
  if (response.status === 204) return undefined as T
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body.message === 'string' ? body.message : 'The request could not be completed.')
  return body as T
}
export const saveConfig = (id: string, configuration: Configuration, discardResults = false) => request<Project>(`/projects/${id}/configuration?discard_results=${discardResults}`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configuration),
})
