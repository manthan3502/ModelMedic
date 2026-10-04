import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../src/App'
import type { Column, Project } from '../src/api/projects'

function fixture(): Project {
  const classes = [{ label: 'no', count: 100, proportion: .5 }, { label: 'yes', count: 100, proportion: .5 }]
  const column = (feature_id: string, name: string, extra: Partial<Column> = {}): Column => ({ feature_id, name, inferred_type: 'numeric', missing_count: 0, distinct_count: 2, samples: ['0', '1'], flags: [], unsupported_reason: null, allowed_types: ['numeric', 'categorical'], target: { eligible: false, classes: [], reasons: ['Target is ineligible'] }, ...extra })
  return { id: 'project1', name: 'Synthetic project', description: 'Test only', state: 'DRAFT', deletion_pending: false, created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z', configuration: {}, limits: { upload_max_bytes: 26214400, max_rows: 50000, max_columns: 100, max_features: 50, max_categories: 100, max_encoded_columns: 2000 },
    dataset: { id: 'dataset1', status: 'READY', canonical_sha256: 'a'.repeat(64), canonical_schema_version: 'canonical-v1', validation_report: { errors: [], warnings: [] }, profile: { row_count: 200, column_count: 4, duplicate_rows: 0,
      columns: [column('f000', 'amount', { flags: ['Review feature type — this feature may represent categories.'] }), column('f001', 'segment', { inferred_type: 'categorical', allowed_types: ['categorical'] }), column('f002', 'outcome', { inferred_type: 'categorical', allowed_types: ['categorical'], target: { eligible: true, reasons: [], classes } }), column('f003', 'timestamp', { allowed_types: [], unsupported_reason: 'Datetime features are unsupported.', flags: ['Datetime features are unsupported.'] })], preview: [['0', 'group', 'yes', '<script>escaped</script>']] } },
    job: { id: 'job1', state: 'SUCCEEDED', stage: 'COMPLETE', error_message: null }, preprocessing: null, confirmation: null }
}

function setup(route: string, initial = fixture()) {
  let project = initial
  const validated = fixture()
  const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST' && url === '/api/v1/projects') project = { ...project, dataset: null, job: null }
    if (url.endsWith('/baseline') && init?.method === 'POST') project = validated
    if (init?.method === 'PUT') {
      project = { ...project, configuration: JSON.parse(init.body as string), preprocessing: { steps: ['Raw columns', 'Handle missing values', 'Encode categories', 'Scale numeric values when required', 'Classifier'], numeric: 'Median imputation. StandardScaler for Logistic Regression only.', categorical: 'Explicit missing category and one-hot encoding.', learning: 'Learned from the Development 80% only.', frozen: 'Frozen after baseline establishment.', fitted: false }, confirmation: null }
      if (project.configuration.classifier) project.confirmation = { ready: true, training_available: false, split: 'Stratified 80/20', cv: '5-fold Development CV', seed: 42, guardrail: 'Actual held-out support must be at least 20 rows per class.' }
    }
    return { ok: true, status: 200, json: async () => structuredClone(url === '/api/v1/projects' && !init ? [project] : url.endsWith('/health/ready') ? { status: 'ready' } : project) }
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>)
  return fetchMock
}

describe('M1 baseline setup', () => {
  it('creates, uploads, reviews and reaches confirmation without training', async () => {
    const fetchMock = setup('/projects/new')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Name'), 'Synthetic project')
    await user.click(screen.getByRole('button', { name: 'Create project and upload baseline' }))
    await screen.findByRole('heading', { name: 'Upload Baseline CSV' })
    await user.upload(screen.getByLabelText('Drop a CSV here or choose a file'), new File(['amount,outcome\n0,yes\n'], 'synthetic.csv', { type: 'text/csv' }))
    await user.click(screen.getByRole('button', { name: 'Upload and validate' }))
    await user.click(await screen.findByRole('link', { name: 'Review dataset profile' }))
    expect(screen.getAllByText('Review feature type — this feature may represent categories.', { exact: false })[0]).toBeVisible()
    expect(screen.getByText('<script>escaped</script>')).toBeVisible()
    expect(document.querySelector('script')).toBeNull()
    await user.click(screen.getByRole('link', { name: 'Select target and configure features' }))
    await user.selectOptions(screen.getByLabelText('Target'), 'f002')
    expect(screen.getByRole('button', { name: 'Review preprocessing' })).toBeDisabled()
    expect(screen.getByLabelText('Include timestamp')).toBeDisabled()
    expect(screen.getByLabelText('Include timestamp')).not.toBeChecked()
    await user.selectOptions(screen.getByLabelText('Binary positive class (required)'), 'yes')
    await user.selectOptions(screen.getByLabelText('Type for amount'), 'categorical')
    await user.click(screen.getByRole('button', { name: 'Review preprocessing' }))
    expect(await screen.findByRole('heading', { name: 'Preprocessing Review' })).toBeVisible()
    expect(screen.getByText('Learned from the Development 80% only.')).toBeVisible()
    await user.click(screen.getByRole('link', { name: 'Select classifier and weighting' }))
    expect(screen.getAllByRole('radio')).toHaveLength(5)
    expect(screen.getByRole('button', { name: 'Review and train' })).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: /Random Forest/ }))
    await user.click(screen.getByRole('radio', { name: 'Balanced' }))
    await user.click(screen.getByRole('button', { name: 'Review and train' }))
    expect(await screen.findByRole('heading', { name: 'Training Confirmation' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Train baseline' })).toBeDisabled()
    expect(screen.getByText('Stratified 80/20')).toBeVisible()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/train'))).toBe(false)
  })

  it('shows validation rejection and leaves later steps unavailable', async () => {
    const p = fixture()
    p.dataset!.status = 'VALIDATION_FAILED'
    p.dataset!.profile = null
    p.dataset!.validation_report = { errors: ['Column names beginning __mm_ are reserved. Rename these columns.'], warnings: [] }
    setup('/projects/project1/setup/upload', p)
    expect(await screen.findByRole('alert')).toHaveTextContent('__mm_')
    expect(screen.queryByRole('link', { name: /Target & features/ })).not.toBeInTheDocument()
  })

  it('handles a failed job and resumes stage polling after refresh', async () => {
    const p = fixture()
    p.dataset!.status = 'UPLOADED'
    p.dataset!.profile = null
    p.job!.state = 'RUNNING'
    p.job!.stage = 'READING_FILE'
    setup('/projects/project1/setup/upload', p)
    expect(await screen.findByText(/Validating baseline: Reading file/)).toHaveAttribute('role', 'status')
    expect(screen.getByRole('button', { name: 'Upload and validate' })).toBeDisabled()
  })

  it('displays backend configuration errors without advancing', async () => {
    setup('/projects/project1/setup/features')
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('Target'), 'f002')
    await user.selectOptions(screen.getByLabelText('Binary positive class (required)'), 'yes')
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ message: 'Encoded-column estimate exceeds limit.' }), { status: 422 }))
    await user.click(screen.getByRole('button', { name: 'Review preprocessing' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Encoded-column')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Target & Features' })).toBeVisible())
  })
})
