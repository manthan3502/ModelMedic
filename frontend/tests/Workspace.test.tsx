import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { App } from '../src/App'
import { Evidence, SignalStatus } from '../src/Scientific'
import { ApiError } from '../src/api/projects'
import { ErrorState, MutationGate, MutationLink, DemoBadge, SyntheticLabel } from '../src/Workspace'
import { demoExplanation, RuntimeContext } from '../src/runtime'

function show(children: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>)
}
describe('M6 shared scientific presentation and demo safety', () => {
  it.each(['DETECTED', 'NOT DETECTED', 'INSUFFICIENT DATA', 'UNAVAILABLE'])('labels %s with an icon and readable text', status => {
    show(<SignalStatus status={status} />)
    expect(screen.getByLabelText(`Scientific status: ${status}`)).toHaveTextContent(status)
    expect(document.querySelector('[aria-hidden=true]')).not.toBeEmptyDOMElement()
    expect(document.querySelector('.signal-status')).toHaveClass(status.toLowerCase().replaceAll(' ', '-'))
  })
  it('renders the five evidence fields in one semantic frame', () => {
    show(<Evidence measured="Raw distributions" result={<SignalStatus status="NOT DETECTED" />} evidence="Saved counts" may="Evidence for these samples" cannot="No equality or causal claim" />)
    expect(screen.getByRole('region', { name: 'Evidence frame' })).toBeVisible()
    expect(Array.from(document.querySelectorAll('dt'), e => e.textContent)).toEqual(['Measured', 'Result', 'Evidence', 'May conclude', 'Cannot conclude'])
  })
  it('explains disabled mutations while preserving read-only navigation', async () => {
    const mutate = vi.fn()
    show(<RuntimeContext.Provider value={{ deployment_mode: 'DEMO_MODE', read_only: true }}><DemoBadge /><SyntheticLabel /><MutationLink to="/projects/new">New project</MutationLink><MutationGate><button onClick={mutate}>Train</button><input aria-label="CSV" type="file" /></MutationGate></RuntimeContext.Provider>)
    expect(screen.getByText('READ-ONLY DEMO')).toBeVisible()
    expect(screen.getByText('Synthetic demo data')).toBeVisible()
    expect(screen.getAllByText(demoExplanation).length).toBe(2)
    expect(screen.getByRole('button', { name: 'New project' })).toBeDisabled()
    expect(screen.getByLabelText('CSV')).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Train' }))
    expect(mutate).not.toHaveBeenCalled()
  })
  it('fails closed while deployment configuration is missing', () => {
    show(<RuntimeContext.Provider value={null}><MutationGate><button>Upload</button></MutationGate></RuntimeContext.Provider>)
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByText(/Saved results remain unchanged/)).toBeVisible()
  })
  it('retains request IDs and safe recovery instructions', () => {
    show(<ErrorState error={new ApiError('Incompatible artifact', 409, 'REQUEST_ERROR', 'request-test')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Incompatible artifact')
    expect(screen.getByRole('alert')).toHaveTextContent('request-test')
    expect(screen.getByRole('alert')).toHaveTextContent('saved results remain unchanged')
  })
  it('loads demo state from the API and blocks a direct create route', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ deployment_mode: 'DEMO_MODE', read_only: true })))
    vi.stubGlobal('fetch', fetcher)
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/projects/new']}><App /></MemoryRouter></QueryClientProvider>)
    await screen.findByText('READ-ONLY DEMO')
    await waitFor(() => expect(screen.getByLabelText('Name')).toBeDisabled())
    expect(screen.getByRole('button', { name: 'Create project and upload baseline' })).toBeDisabled()
    expect(fetcher).toHaveBeenCalledWith('/api/v1/runtime', undefined)
    expect(fetcher.mock.calls.every(([, init]) => !init?.method)).toBe(true)
  })
})
