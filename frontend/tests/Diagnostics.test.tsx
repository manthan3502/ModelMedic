import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { reportPrintStyles } from '../src/reportPrint'
import { ReportView, SliceResults, Slices, TrendChart, Trends } from '../src/Diagnostics'
import { Methodology } from '../src/Methodology'
import type { ReportData, SliceAnalysis, TrendsData } from '../src/api/diagnostics'

const limitation = 'Slice comparisons are exploratory. ModelMedic does not perform significance testing or multiplicity correction across slices. Apparent differences may reflect sampling variation. This is not a fairness audit.'
const insufficient = 'Insufficient sample size for stable slice analysis.'
const analysis: SliceAnalysis = { id: 's', feature_id: 'f001', feature_name: 'segment', methodology_version: 'slices-v1', code_version: 'a'.repeat(40), status: 'READY', published_at: '2026-10-05', limitation, job: { state: 'SUCCEEDED', stage: 'COMPLETE', error_message: null }, rows: [
  { slice_key: 'all', slice_value: null, is_overall: true, row_count: 100, class_support: { a: 50, b: 50 }, metrics: { balanced_accuracy: { value: .8, reason: null }, brier: { value: .1, reason: null } }, status: 'AVAILABLE', reason: null },
  { slice_key: 'small', slice_value: ' raw ', is_overall: false, row_count: 29, class_support: { a: 10, b: 19 }, metrics: {}, status: 'INSUFFICIENT DATA', reason: insufficient },
  { slice_key: 'large', slice_value: 'raw', is_overall: false, row_count: 71, class_support: { a: 40, b: 31 }, metrics: { balanced_accuracy: { value: .7, reason: null }, brier: { value: .2, reason: null } }, status: 'AVAILABLE', reason: null },
] }
const history: TrendsData = { group: 'performance', signal: 'balanced_accuracy', options: { performance: ['balanced_accuracy', 'f1'], probability: ['brier', 'log_loss'], confidence: ['median', 'mean'], predictions: ['class_share'], data: ['ks', 'js', 'missing_percent'] }, features: [{ feature_id: 'f000', name: 'amount', type: 'numeric' }, { feature_id: 'f001', name: 'segment', type: 'categorical' }], class_order: ['b', 'a'], reference: { label: 'Baseline — held-out reference', value: .9, n: 60, status: 'AVAILABLE', reason: null }, warning: 'Methodology versions differ across these runs. Direct comparison may require care. Historical values have not been recomputed.', limitation: 'One stored signal at a time.', points: [
  { run_id: 'b1', name: 'First labeled', monitoring_date: '2026-10-01', mode: 'B', value: .8, n: 120, status: 'AVAILABLE', reason: null, adjusted_p: null },
  { run_id: 'a', name: 'Unlabeled gap', monitoring_date: '2026-10-02', mode: 'A', value: null, n: null, status: 'UNAVAILABLE', reason: 'Unavailable — ground-truth labels were not provided.', adjusted_p: null },
  { run_id: 'b2', name: 'Second labeled', monitoring_date: '2026-10-03', mode: 'B', value: .7, n: 100, status: 'AVAILABLE', reason: null, adjusted_p: null },
] }
function show(element: React.ReactNode) { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>) }

describe('M5 slices', () => {
  it('keeps raw spellings, All rows, support and insufficiency in the table but omits small groups from the plot', async () => {
    show(<SliceResults analysis={analysis} />)
    expect(screen.getByText(limitation)).toBeVisible()
    expect(screen.getByText(insufficient)).toBeVisible()
    expect(screen.getByRole('row', { name: /" raw " 29/ })).toHaveTextContent('a: 10 · b: 19')
    expect(screen.getByRole('row', { name: /All rows 100/ })).toHaveTextContent('0.8000')
    const chart = screen.getByRole('img', { name: /One metric:/ })
    expect(chart.querySelectorAll('circle')).toHaveLength(1)
    expect(within(chart).queryByText(/ raw /)).not.toBeInTheDocument()
    await userEvent.setup().selectOptions(screen.getByLabelText('Metric for dot plot'), 'brier')
    expect(chart).toHaveAccessibleName(/Brier Score/)
    expect(document.body.textContent).not.toMatch(/worst slice|fairness verdict|retrain now/i)
  })
  it('uses an explicit worker action and revisits the saved feature without another job', async () => {
    let created = false
    const fetcher = vi.fn().mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') { created = true; return { ok: true, status: 202, json: async () => analysis } }
      return { ok: true, status: 200, json: async () => ({ status: 'AVAILABLE', limitation, eligible_features: [{ feature_id: 'f001', name: 'segment' }], analyses: created ? [analysis] : [] }) }
    })
    vi.stubGlobal('fetch', fetcher)
    show(<Slices runId="r" />)
    const button = await screen.findByRole('button', { name: 'Analyze Slices' })
    expect(fetcher.mock.calls.filter(c => c[1]?.method === 'POST')).toHaveLength(0)
    await userEvent.setup().click(button)
    expect(await screen.findByRole('button', { name: 'segment · READY' })).toBeVisible()
    expect(button).toBeDisabled()
    await userEvent.setup().click(screen.getByRole('button', { name: 'segment · READY' }))
    expect(fetcher.mock.calls.filter(c => c[1]?.method === 'POST')).toHaveLength(1)
  })
})

describe('M5 trends', () => {
  it('renders B-A-B gaps without line segments, smoothing or interpolated points', () => {
    show(<TrendChart data={history} />)
    const chart = screen.getByRole('img', { name: /Separate observed points/ })
    expect(chart.querySelectorAll('circle')).toHaveLength(3) // includes held-out reference
    expect(chart.querySelectorAll('polyline, line')).toHaveLength(0)
    expect(chart.querySelectorAll('path')).toHaveLength(1) // axes only
    expect(within(chart).getByText('Unavailable')).toBeVisible()
  })
  it('requests exactly one signal and the correct frozen feature/class selector, preserving version caution', async () => {
    const fetcher = vi.fn().mockImplementation(async (url: string) => {
      const params = new URL(url, 'http://localhost').searchParams
      return { ok: true, status: 200, json: async () => ({ ...history, group: params.get('group') ?? 'confidence', signal: params.get('signal') ?? 'median', reference: ['ks', 'js'].includes(params.get('signal') ?? '') ? null : history.reference }) }
    })
    vi.stubGlobal('fetch', fetcher)
    show(<Trends projectId="p" />)
    const group = await screen.findByLabelText('Signal group')
    expect(await screen.findByText(history.warning!)).toBeVisible()
    await userEvent.setup().selectOptions(group, 'performance')
    expect(await screen.findByRole('row', { name: /Unlabeled gap/ })).toHaveTextContent('Unavailable')
    await userEvent.setup().selectOptions(group, 'data')
    await waitFor(() => expect(fetcher).toHaveBeenLastCalledWith('/api/v1/projects/p/trends?group=data&signal=ks&feature_id=f000', undefined))
    await userEvent.setup().selectOptions(screen.getByLabelText('Signal', { exact: true }), 'js')
    expect(await screen.findByText('No baseline self-comparison point is created for KS/JS.')).toBeVisible()
    expect(screen.getByLabelText('Frozen model feature')).toHaveValue('f001')
    await userEvent.setup().selectOptions(group, 'predictions')
    expect(screen.getByLabelText('Frozen class')).toHaveValue('b')
    await userEvent.setup().selectOptions(screen.getByLabelText('Frozen class'), 'a')
    await waitFor(() => expect(fetcher).toHaveBeenLastCalledWith('/api/v1/projects/p/trends?group=predictions&signal=class_share&class_label=a', undefined))
  })
})

it('prints a single-column stored report with section jumps, evidence fields, table alternatives and exact footer', async () => {
  const print = vi.fn()
  vi.stubGlobal('print', print)
  const footer = 'Generated from stored results using fixed reviewed templates. No language model generated this report.'
  const data: ReportData = { report: { report_template_version: 'report-v1', methodology_version: 'monitoring-v1', code_version: 'a'.repeat(40), source_code_version: 'a'.repeat(40), generated_at: '2026-10-05', footer, sections: [{ key: 'data', title: 'Data changes', paragraphs: ['ModelMedic does not claim this feature change caused any change in performance.'], tables: [{ caption: 'Separate evidence', columns: ['Feature', 'Type', 'Status', 'Test', 'n', 'Raw p', 'Adjusted p'], rows: [['amount', 'numeric', 'DETECTED', 'KS', 100, .001, .002]] }], findings: [{ measured: 'Raw distributions', result: 'DETECTED', evidence: 'n = 100', may_conclude: 'Evidence of difference', cannot_conclude: 'No causality' }] }] }, slice_analyses: [] }
  show(<ReportView data={data} />)
  expect(screen.getByRole('link', { name: 'Data changes' })).toHaveAttribute('href', '#report-data')
  for (const field of ['Measured', 'Result', 'Evidence', 'May conclude', 'Cannot conclude']) expect(screen.getByText(field)).toBeVisible()
  expect(screen.getByText(footer)).toBeVisible()
  expect(document.querySelector('.print-table-alternative')).toHaveTextContent('Adjusted p')
  await userEvent.setup().click(screen.getByRole('button', { name: 'Print / Save as PDF' }))
  expect(print).toHaveBeenCalledOnce()
  const css = reportPrintStyles
  await userEvent.setup().click(screen.getByRole('button', { name: 'Preview print layout' }))
  expect(document.querySelector('style')?.textContent?.trim().startsWith('@page')).toBe(true)
  expect(screen.getByRole('button', { name: 'Return to report' })).toBeVisible()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Return to report' }))
  expect(document.querySelector('style')).toHaveTextContent('@media print')
  expect(css).toContain('@page')
  expect(css).toMatch(/\.topbar, \.skip-link, \.run-navigation, \.report-controls[^}]+display: none !important/)
  expect(css).toContain('.report-wide-table { display: none !important; }')
})

it('matches the locked methodology topics and searches the static glossary without API-generated prose', async () => {
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  show(<Methodology />)
  for (const topic of ['Workflow', 'Split / CV', 'Preprocessing', 'Metrics', 'KS / Wasserstein', 'Jensen–Shannon / chi-square', 'Missingness / Fisher exact', 'BH / FDR', 'Predictions / confidence', 'Calibration', 'Permutation importance', 'Slices', 'Guardrails / limitations', 'Glossary']) expect(screen.getByRole('heading', { name: topic })).toBeVisible()
  expect(screen.getByText(/max\(200, 100 × number of target classes\)/)).toBeVisible()
  expect(screen.getByText(/t = 5 × \(n_base \+ n_current\)/)).toBeVisible()
  await userEvent.setup().type(screen.getByLabelText('Search glossary'), 'Fisher')
  expect(screen.getByRole('status')).toHaveTextContent('1 terms')
  expect(fetcher).not.toHaveBeenCalled()
  expect(document.body.textContent).not.toMatch(/later milestone|AutoML recommendation|retrain now/i)
})
