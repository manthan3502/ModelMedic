import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../src/App'

function setup(route = '/projects', offline = false) {
  const fetchMock = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url.endsWith('/runtime') ? { deployment_mode: 'FULL_MODE', read_only: false } : url.endsWith('/projects') ? [] : ({ status: 'ready' }) }))
  if (offline) fetchMock.mockRejectedValue(new Error('offline'))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[route]}><App /></MemoryRouter>
  </QueryClientProvider>)
}

describe('M0 shell', () => {
  it('renders the shell and checks the real readiness endpoint', async () => {
    setup('/')
    expect(await screen.findByRole('heading', { name: 'Projects', level: 1 })).toBeVisible()
    expect(screen.getByRole('link', { name: 'ModelMedic' })).toBeVisible()
    expect(await screen.findByRole('link', { name: 'New project' })).toHaveAttribute('href', '/projects/new')
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/health/ready'))
  })
  it('navigates with accessible links and restores reading context', async () => {
    setup()
    await userEvent.click(screen.getByRole('link', { name: 'Methodology' }))
    expect(screen.getByRole('heading', { name: 'Methodology', level: 1 })).toBeVisible()
    expect(screen.getByRole('main')).toHaveFocus()
    expect(document.title).toBe('Methodology · ModelMedic')
    await userEvent.click(screen.getByRole('link', { name: 'Back to Projects' }))
    expect(screen.getByRole('heading', { name: 'Projects', level: 1 })).toBeVisible()
  })
  it('shows a useful not-found route', () => {
    setup('/missing')
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  })
  it('shows loading and a recoverable API error without invented data', async () => {
    setup('/projects', true)
    expect(screen.getByRole('status')).toHaveTextContent('Connecting')
    await screen.findByRole('alert')
    vi.mocked(fetch).mockImplementation(async (url) => new Response(JSON.stringify(String(url).endsWith('/projects') ? [] : { status: 'ready' })))
    await userEvent.click(screen.getByRole('button', { name: 'Retry connection' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })
})
