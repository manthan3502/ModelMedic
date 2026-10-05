import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request } from './api/projects'
import { PresentationContext, type Interpretation } from './interpretationContext'
import { ErrorState } from './Workspace'

export function PresentationProvider({ runId, children }: { runId: string; children: ReactNode }) {
  const query = useQuery({ queryKey: ['presentation', runId], queryFn: () => request<Record<string, Interpretation>>(`/runs/${runId}/presentation`) })
  return <PresentationContext.Provider value={query.data ?? null}>{query.isError && <ErrorState error={query.error} retry={() => void query.refetch()} />}{children}</PresentationContext.Provider>
}
