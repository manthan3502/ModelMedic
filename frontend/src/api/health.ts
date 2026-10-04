export async function readReadiness(): Promise<boolean> {
  const response = await fetch('/api/v1/health/ready')
  if (!response.ok) throw new Error('The workspace service is unavailable.')
  const payload: { status?: string } = await response.json()
  if (payload.status !== 'ready') throw new Error('The workspace service is not ready.')
  return true
}
