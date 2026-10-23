export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: 'kadr-api'
  version: string
  database: 'ok' | 'unavailable'
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/v1/system/health', {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`)
  }
  return (await response.json()) as HealthResponse
}

