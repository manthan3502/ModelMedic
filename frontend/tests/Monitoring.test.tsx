import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AnalysisProgress, Confidence, DataResults, FeatureDetail, ModeAUnavailable, MonitoringWorkspace, Predictions, RunReview } from '../src/Monitoring'
import { modeALimitation, type FeatureResult, type MonitoringResults, type Run } from '../src/api/monitoring'

const signal = { baseline_n: 100, current_n: 50, test: 'KS two-sample', statistic: .6, raw_p: .001, adjusted_p: .002, status: 'DETECTED', bh_family_size: 2 }
const plot = { bins: [{ lower: 0, upper: 1, baseline_count: 100, current_count: 50, baseline_share: 1, current_share: 1 }], reason: null }
const feature: FeatureResult = { feature_id: 'f000', name: 'amount', type: 'numeric', distribution: { ...signal, distance_name: 'Wasserstein-1', distance: 10, baseline_min: 0, baseline_max: 20, outside_range_share: .2, warnings: ['Tied/discrete numeric feature: the continuous KS assumption is imperfect.'], plot }, missingness: { ...signal, status: 'NOT DETECTED', baseline_missing_count: 0, current_missing_count: 0, baseline_missing_percent: 0, current_missing_percent: 0, delta_pp: 0 }, reliance: { feature: 'amount', mean: -.03, sd: .02 } }
const data = { frozen_statement: '', baseline_snapshot_id: 's', code_version: 'c', methodology_version: 'monitoring-v1', canonical_sha256: 'h', missingness_detected: 0, validation: { errors: [], warnings: [] }, limitations: [], mode: 'A', limitation: modeALimitation, data_reference: 'Baseline — all valid baseline rows', model_reference: 'Baseline — held-out reference', counts: { DETECTED: 1 }, tested_features: 1, bh_family_size: 2, features: [feature], predictions: { class_order: ['b', 'a'], ...signal, distance_name: 'Jensen-Shannon (base 2)', distance: .2, interpretation: 'Prediction distribution changed.', limitation: 'Prediction shift does not tell you whether the predictions are correct.', categories: [{ category: 'b', baseline_count: 80, current_count: 10, baseline_share: .8, current_share: .2, delta_pp: -60 }, { category: 'a', baseline_count: 20, current_count: 40, baseline_share: .2, current_share: .8, delta_pp: 60 }] }, confidence: { ...signal, baseline_mean: .8, current_mean: .6, baseline_median: .8, current_median: .6, plot, limitation: 'Confidence change does not prove accuracy or calibration changed.' } } as MonitoringResults
const run = { id: 'r', state: 'READY', mode: 'A', row_count: 50, project_id: 'p', dataset: { validation_report: { errors: [], warnings: ['Extra columns ignored.'], ignored_extra_columns: ['extra'], required_features: ['amount'], coercions: [], new_categories: [] } }, job: { state: 'SUCCEEDED', stage: 'COMPLETE' } } as unknown as Run
function show(element: React.ReactNode) { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>) }

describe('M3 Mode A', () => {
  it('requires explicit analysis after mode/compatibility review and never trains', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202, json: async () => run })
    vi.stubGlobal('fetch', fetchMock)
    show(<RunReview run={run} />)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('Mode A — labels unavailable')).toBeVisible()
    expect(screen.getByText(modeALimitation)).toBeVisible()
    expect(screen.getByText(/Extra columns ignored for the model: extra/)).toBeVisible()
    expect(screen.getByText(/Nothing is retrained, refitted or updated/)).toBeVisible()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Analyze current data' }))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/runs/r/analyze', { method: 'POST' })
  })
  it('reports meaningful progress without percentages or partial scientific output', () => {
    show(<AnalysisProgress run={{ ...run, job: { id: 'j', state: 'RUNNING', stage: 'DATA_DRIFT', error_message: null, started_at: null } }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Analyzing data distributions')
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument()
    expect(screen.getByText(/No final scientific results/)).toBeVisible()
  })
  it('keeps distribution, missingness and baseline reliance distinct with evidence and full feature detail', async () => {
    show(<DataResults data={data} runId="r" />)
    expect(screen.getByRole('link', { name: 'amount' })).toHaveAttribute('href', '/runs/r/features/f000')
    expect(screen.getByText(/BH family size 2/)).toBeVisible()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Missingness' }))
    expect(screen.getByText(/ordered by absolute percentage-point/)).toBeVisible()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Reliance × change' }))
    expect(screen.getByText('-0.0300 ± 0.0200')).toBeVisible()
  })
  it('names raw all-row reference and preserves negative reliance, caution, sample sizes and chart alternative', () => {
    show(<FeatureDetail feature={feature} reference={data.data_reference} />)
    expect(screen.getByText(/Baseline — all valid baseline rows/)).toBeVisible()
    expect(screen.getByText(/Mean -0.0300/)).toBeVisible()
    expect(screen.getByText(/continuous KS assumption is imperfect/)).toBeVisible()
    expect(screen.getAllByText(/Baseline n = 100 · Current n = 50/)).toHaveLength(2)
    expect(screen.getByRole('img', { name: /Shared-bin normalized histogram/ })).toBeVisible()
    expect(screen.getByText(/Shared baseline-derived bins/)).toBeVisible()
    expect(screen.getByText('ModelMedic does not claim this feature change caused any change in performance.')).toBeVisible()
  })
  it('renders prediction shares in frozen order and does not claim correctness', () => {
    show(<Predictions data={data} />)
    expect(screen.getByText('Prediction distribution changed.')).toBeVisible()
    expect(screen.getByText(data.predictions.limitation)).toBeVisible()
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('b')
    expect(screen.getAllByRole('row')[2]).toHaveTextContent('a')
  })
  it('uses fixed confidence probability axis, held-out reference and required limitation', () => {
    show(<Confidence data={data} />)
    expect(screen.getByRole('img', { name: /Fixed probability axis 0 to 1/ })).toBeVisible()
    expect(screen.getByText(/Maximum predicted class probability · Baseline — held-out reference/)).toBeVisible()
    expect(screen.getByText(data.confidence.limitation)).toBeVisible()
  })
  it.each(['Performance', 'Calibration', 'Classes & errors', 'Slices'])('explains %s unavailability without fake charts or prohibited claims', name => {
    show(<ModeAUnavailable name={name} />)
    expect(screen.getByText(modeALimitation)).toBeVisible()
    expect(screen.getByRole('heading', { name })).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/performance degraded|accuracy fell|model is failing|model is unreliable|calibration worsened|retraining is required|retrain now/i)
  })
})


it('opens the dedicated Feature Detail route rather than run Overview', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => ({ ok: true, status: 200, json: async () => path.endsWith('/summary') ? data : { ...run, state: 'ANALYZED', name: 'Current run', monitoring_date: '2026-10-04', baseline_snapshot_id: 's' } })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/runs/r/features/f000']}><Routes><Route path="/runs/:runId/features/:featureId" element={<MonitoringWorkspace />} /></Routes></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'amount' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Run Overview' })).not.toBeInTheDocument()
})


it('shows validation separately before mode review and never implies automatic analysis', () => {
  show(<RunReview run={{ ...run, state: 'UPLOADED', mode: null, dataset: null, job: { id: 'j', state: 'QUEUED', stage: 'WAITING', error_message: null, started_at: null } }} />)
  expect(screen.getByRole('status')).toHaveTextContent('Validating current CSV: Waiting for worker')
  expect(screen.getByRole('status')).toHaveTextContent('explicit Analyze action')
  expect(screen.queryByRole('heading', { name: 'Analysis progress' })).not.toBeInTheDocument()
})
