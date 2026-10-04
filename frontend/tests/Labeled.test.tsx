import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { LabeledPerformance, LabeledCalibration, LabeledErrors } from '../src/Labeled'
import { AnalysisProgress, RunReview, MonitoringWorkspace } from '../src/Monitoring'
import type { PerformanceResults, CalibrationResults, ErrorsResults, Comparison } from '../src/api/labeled'
import type { Run } from '../src/api/monitoring'

const limitation = 'Small metric differences may reflect sampling variation. ModelMedic V1 does not estimate uncertainty intervals for performance changes.'
const m: Comparison = { metric_name: 'balanced_accuracy', class_label: null, baseline_value: .8, current_value: null, delta: null, baseline_support: 60, current_support: 50, status: 'UNAVAILABLE', reason: 'Not all frozen classes have current support.', note: null }
const performance: PerformanceResults = { metrics: [m, { ...m, metric_name: 'log_loss', current_value: .7, delta: -.1, status: 'AVAILABLE', reason: null, note: 'Class composition changed; aggregate probability-metric deltas should be interpreted cautiously because the absent class has no current outcome support.' }], per_class: [], class_order: ['Gold', 'Silver', 'Bronze'], baseline_n: 60, current_n: 50, absent_classes: ['Gold'], warnings: ['Absent current classes: Gold'], limitation, class_composition: [{ category: 'Gold', baseline_count: 20, current_count: 0, baseline_share: 1/3, current_share: 0, delta_pp: -100/3 }] }
const curve = { class: 'Gold', positive_count: 20, non_positive_count: 40, reason: null, bins: [{ mean_probability: .5, observed_rate: .4, count: 60 }] }
const calibration: CalibrationResults = { class_order: ['Gold', 'Silver'], baseline: { support: 60, requested_bins: 3, warning: 'Limited-support calibration estimate — empirical rates may be unstable.', classes: [curve, { ...curve, class: 'Silver' }] }, current: { support: 50, requested_bins: 3, warning: 'Limited-support calibration estimate — empirical rates may be unstable.', classes: [{ ...curve, positive_count: 0, non_positive_count: 50, reason: 'Unavailable — insufficient positive/non-positive observations.', bins: [] }, { ...curve, class: 'Silver', bins: [{ mean_probability: .6, observed_rate: .7, count: 50 }] }] }, metrics: [{ ...m, metric_name: 'brier' }], limitation }
const confusion = { counts: [[10,20],[5,15]], normalized: [[1/3,2/3],[.25,.75]], common_pairs: [], binary: { tp: 10, tn: 15, fp: 5, fn: 20 } }
const errors: ErrorsResults = { class_order: ['yes','no'], positive_class: 'yes', baseline: confusion, current: confusion, row_references: { fp: [7], fn: [8] }, example_limit: 50, normalization: 'Row-normalized by actual-class support; no support is Unavailable.' }
const run = { id: 'r', project_id: 'p', state: 'READY', mode: 'B', row_count: 50, dataset: { validation_report: { errors: [], warnings: [], required_features: ['amount'] } }, job: { state: 'SUCCEEDED', stage: 'COMPLETE' } } as unknown as Run
function show(element: React.ReactNode) { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>) }

it('requires explicit Mode B analysis after visible valid-label review', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202, json: async () => run })
  vi.stubGlobal('fetch', fetchMock)
  show(<RunReview run={run} />)
  expect(fetchMock).not.toHaveBeenCalled()
  expect(screen.getByText('Mode B — labels available')).toBeVisible()
  expect(screen.getByText(/Nothing is retrained, refitted or updated/)).toBeVisible()
  const button = screen.getByRole('button', { name: 'Analyze current data' })
  expect(button).toBeEnabled()
  await userEvent.setup().click(button)
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/runs/r/analyze', { method: 'POST' })
})
it('adds performance and calibration stages only for Mode B without fake percentages', () => {
  show(<AnalysisProgress run={{ ...run, job: { id: 'j', state: 'RUNNING', stage: 'PERFORMANCE', error_message: null, started_at: null } }} />)
  expect(screen.getByRole('status')).toHaveTextContent('Measuring performance')
  expect(screen.getByText('Analyzing calibration')).toBeVisible()
  expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument()
})
it('Mode A still skips both labeled stages', () => {
  show(<AnalysisProgress run={{ ...run, mode: 'A' }} />)
  expect(screen.queryByText('Measuring performance')).not.toBeInTheDocument()
  expect(screen.queryByText('Analyzing calibration')).not.toBeInTheDocument()
})
it('renders class mix before neutral performance tables, explicit unavailability and support', () => {
  show(<LabeledPerformance data={performance} />)
  expect(screen.getAllByText(limitation)[0]).toBeVisible()
  expect(screen.getByText('Absent current classes: Gold')).toBeVisible()
  const tables = screen.getAllByRole('table')
  expect(tables[0]).toHaveTextContent('True labels')
  expect(tables[1]).toHaveTextContent('UNAVAILABLE')
  expect(tables[1]).toHaveTextContent('Not all frozen classes have current support.')
  expect(tables[1]).toHaveTextContent('Baseline support')
  expect(tables[1]).toHaveTextContent('Current support')
  expect(screen.queryByText(/health score|severe|retrain now|improved|degraded/i)).not.toBeInTheDocument()
})
it('shows historical calibration, absent current class reason, bin support and frozen class selector', async () => {
  show(<LabeledCalibration data={calibration} />)
  expect(screen.getByText('Current: Unavailable — insufficient positive/non-positive observations.')).toBeVisible()
  expect(screen.getAllByText(/Limited-support calibration estimate/)).toHaveLength(2)
  expect(screen.getByRole('img', { name: /Baseline and Current reliability diagram/ })).toBeVisible()
  expect(screen.getByRole('img', { name: /Baseline bin 1.*n=60/ })).toHaveAttribute('tabindex', '0')
  const selector = screen.getByRole('combobox', { name: 'One-vs-Rest class' })
  expect(within(selector).getAllByRole('option').map(o => o.textContent)).toEqual(['Gold','Silver'])
  await userEvent.setup().selectOptions(selector, 'Silver')
  expect(screen.getByRole('img', { name: /Current bin 1.*n=50/ })).toBeVisible()
  expect(screen.getByText(/Probabilistic prediction quality/)).toBeVisible()
  expect(screen.queryByText(/well calibrated|poorly calibrated|calibration score|recalibrate/i)).not.toBeInTheDocument()
})
it('fetches bounded canonical examples, escapes cells, excludes identifiers and toggles confusion counts', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ features: ['category'], rows: [{ row_id: 7, features: { category: '<img src=x onerror=alert(1)>', excluded_id: 'hidden' } }] }) })
  vi.stubGlobal('fetch', fetchMock)
  show(<LabeledErrors data={errors} runId="r" />)
  expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeVisible()
  expect(document.querySelector('img')).toBeNull()
  expect(screen.queryByText('hidden')).not.toBeInTheDocument()
  expect(screen.queryByText('excluded_id')).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/runs/r/errors/examples?view=fp', undefined)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Show counts' }))
  expect(screen.getByText(/Baseline confusion matrix.*counts/)).toBeVisible()
  await userEvent.setup().click(screen.getByRole('button', { name: 'False Negatives' }))
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/runs/r/errors/examples?view=fn', undefined)
})
it('routes Mode B Performance to measured data', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => ({ ok: true, status: 200, json: async () => path.endsWith('/summary') ? { mode: 'B', performance, features: [] } : { ...run, state: 'ANALYZED', name: 'Labeled run', monitoring_date: '2026-10-05' } })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/runs/r/performance']}><Routes><Route path="/runs/:runId/:section" element={<MonitoringWorkspace />} /></Routes></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'Performance' })).toBeVisible()
  expect(screen.getByText('Not all frozen classes have current support.')).toBeVisible()
  expect(screen.getByText(/Labels were provided, so performance and calibration were measured/)).toBeVisible()
  expect(screen.queryByText(/Why unavailable/)).not.toBeInTheDocument()
})

it('keeps Mode A Performance explicitly Unavailable after M4', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => ({ ok: true, status: 200, json: async () => path.endsWith('/summary') ? { mode: 'A', features: [] } : { ...run, mode: 'A', state: 'ANALYZED', name: 'Unlabeled run', monitoring_date: '2026-10-05' } })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/runs/r/performance']}><Routes><Route path="/runs/:runId/:section" element={<MonitoringWorkspace />} /></Routes></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'Why unavailable' })).toBeVisible()
  expect(screen.queryByText('True class composition')).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
