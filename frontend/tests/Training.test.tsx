import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { BaselineResultsView, Establish, TrainAction } from '../src/Training'
import type { BaselineResults, Project } from '../src/api/projects'

const metric = (value: number | null, reason: string | null = null) => ({ value, reason })
const results: BaselineResults = {
  metrics: { support: 60, class_order: ['a', 'b'], metrics: { accuracy: metric(.8), balanced_accuracy: metric(.8), precision: metric(null, 'No predictions for this class.'), brier: metric(.2), log_loss: metric(.4) }, per_class: [{ class: 'a', support: 30, precision: metric(null, 'No predictions for this class.'), recall: metric(0), f1: metric(0) }], confusion_matrix: [[0,30],[0,30]] },
  cv: { accuracy: { values: [.7,.8,.75,.8,.7], mean: .75, sd: .05, min: .7, max: .8, reason: null } },
  calibration: { support: 60, requested_bins: 3, warning: 'Limited-support calibration estimate — empirical rates may be unstable.', classes: [{ class: 'a', positive_count: 30, non_positive_count: 30, reason: null, bins: [{ count: 20, mean_probability: .2, observed_rate: .1 }, { count: 20, mean_probability: .5, observed_rate: .6 }, { count: 20, mean_probability: .8, observed_rate: .8 }] }] },
  importance: [{ feature: 'amount', mean: -.03, sd: .01 }], development_count: 240, heldout_count: 60, class_order: ['a','b'], class_counts: { a:150,b:150 }, development_class_counts: { a:120,b:120 }, heldout_class_counts: { a:30,b:30 }, warnings: [], manifest: { target:'outcome', random_seed:42, code_version:'123' }, features: [],
}
function project(): Project { return { id: 'p', state: 'DRAFT', configuration: { classifier:'logistic_regression',weighting:'standard' }, confirmation: { ready:true,training_available:true,split:'Stratified 80/20',cv:'5-fold',seed:42,guardrail:'20/class' }, baseline: { id:'snapshot',status:'TRAINED',fingerprint:'fingerprint',established_at:null,error_message:null,results } } as Project }
function show(component: React.ReactNode) { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{component}</MemoryRouter></QueryClientProvider>) }

describe('M2 baseline workflow', () => {
  it('requires explicit train action and tracks stages without provisional metrics', async () => {
    const p = { ...project(), baseline:null, job: { id:'j',job_type:'BASELINE_TRAIN',state:'RUNNING',stage:'CROSS_VALIDATING',error_message:null,started_at:new Date().toISOString() } }
    const fetchMock=vi.fn(); vi.stubGlobal('fetch',fetchMock)
    show(<TrainAction p={p} />)
    expect(screen.getByRole('button',{name:'Train baseline'})).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Running 5-fold CV')
    expect(screen.queryByText('Accuracy')).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('shows official results separately from five-fold diagnostics and explicit unavailable reasons', async () => {
    show(<BaselineResultsView p={project()} />)
    const user=userEvent.setup()
    expect(screen.getByText('Official baseline = Held-out Baseline Reference')).toBeVisible()
    await user.click(screen.getByRole('button',{name:'Performance'}))
    expect(screen.getByRole('heading',{name:'Development CV — diagnostics only'})).toBeVisible()
    expect(screen.getByRole('img',{name:/five fold values/})).toBeVisible()
    expect(screen.getAllByText(/Unavailable — No predictions/)).toHaveLength(2)
    await user.click(screen.getByRole('button',{name:'Calibration'}))
    expect(screen.getByText('Limited-support calibration estimate — empirical rates may be unstable.')).toBeVisible()
    expect(screen.getAllByText('20')).toHaveLength(3)
    await user.click(screen.getByRole('button',{name:'Model reliance'}))
    expect(screen.getByRole('heading',{name:'Model reliance estimate — not causal importance.'})).toBeVisible()
    expect(screen.getByText('Mean -0.0300 · SD 0.0100')).toBeVisible()
  })
  it('requires discard confirmation to replace a trained draft and exposes sanitized server rejection', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({message:'The current draft changed. Train it again.'})}))
    show(<TrainAction p={project()} />)
    const user=userEvent.setup()
    expect(screen.getByRole('button',{name:'Train baseline'})).toBeDisabled()
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button',{name:'Train baseline'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('The current draft changed.')
  })
  it('establishment sends the reviewed snapshot and freezes calmly', async () => {
    const fetchMock=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>({...project(),state:'BASELINE_READY'})})
    vi.stubGlobal('fetch',fetchMock)
    show(<Establish p={project()} />)
    expect(screen.getByText('This becomes frozen')).toBeVisible()
    expect(fetchMock).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button',{name:'Establish baseline'}))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/p/establish', expect.objectContaining({method:'POST',body:'{"snapshot_id":"snapshot"}'}))
  })
})
