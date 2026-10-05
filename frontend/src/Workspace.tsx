import { useId, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ApiError, request } from './api/projects'

import { RuntimeContext, useRuntime, demoExplanation, type Runtime } from './runtime'
export function RuntimeProvider({ children }: { children: ReactNode }) {
  const query = useQuery({ queryKey: ['runtime'], queryFn: async () => {
    const data = await request<Runtime>('/runtime')
    if (!['FULL_MODE', 'DEMO_MODE'].includes(data.deployment_mode) || data.read_only !== (data.deployment_mode === 'DEMO_MODE')) throw new Error('Deployment configuration is unavailable.')
    return data
  }, retry: false })
  return <RuntimeContext.Provider value={query.data ?? null}>{children}</RuntimeContext.Provider>
}
export function DemoBadge() {
  const runtime = useRuntime()
  return runtime?.read_only ? <span className="demo-badge">READ-ONLY DEMO</span> : null
}
export function SyntheticLabel() {
  return useRuntime()?.read_only ? <span className="synthetic-label">Synthetic demo data</span> : null
}
export function MutationNotice() {
  const runtime = useRuntime()
  return runtime?.read_only ? <p className="notice demo-notice">{demoExplanation}</p> : !runtime ? <p className="notice">Deployment configuration is unavailable. Saved results remain unchanged. Retry the service connection before making changes.</p> : null
}
export function MutationGate({ children }: { children: ReactNode }) {
  const runtime = useRuntime()
  return <><MutationNotice /><fieldset disabled={!runtime || runtime.read_only}>{children}</fieldset></>
}
export function MutationLink({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  const runtime = useRuntime()
  const explanationId = useId()
  return runtime && !runtime.read_only ? <Link to={to} className={className}>{children}</Link> : <div className="demo-action"><button disabled className="secondary" aria-describedby={explanationId}>{children}</button><p id={explanationId}>{runtime?.read_only ? demoExplanation : 'Deployment configuration must be available before making changes.'}</p></div>
}
export function ErrorState({ error, retry, retryLabel = 'Retry' }: { error?: Error | null; retry?: () => void; retryLabel?: string }) {
  const api = error instanceof ApiError ? error : null
  return <section className="notice error" role="alert"><h2>{api?.status === 404 ? 'Resource not found' : api?.status === 409 ? 'Results unavailable' : 'Request could not be completed'}</h2><p>{error?.message ?? 'The service connection is unavailable.'}</p><p>Established baselines and saved results remain unchanged. No scientific conclusion can be drawn from this error.</p><p>{api?.status === 404 ? 'Return to Projects and choose an existing project or run.' : api?.status === 409 ? 'Review the job or artifact compatibility details. Complete the required workflow in Full Mode before inspecting these results.' : 'Check the API and database connection, then retry. If this persists, use the request ID when reporting it.'}</p>{api?.requestId && <p>Request ID: <span className="mono hash">{api.requestId}</span></p>}{retry && <button className="secondary" onClick={retry}>{retryLabel}</button>} <Link to="/projects">Back to Projects</Link></section>
}
export function NotFound() {
  return <section className="prose"><h1>Page not found</h1><p>This address is not part of the workspace.</p><p>Saved projects and scientific results remain unchanged.</p><Link to="/projects">Back to Projects</Link></section>
}
