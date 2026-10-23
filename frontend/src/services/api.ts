import type { CatalogQuery, Genre, MediaDetails, MediaKind, MediaPage } from '../types/media'

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: 'kadr-api'
  version: string
  database: 'ok' | 'unavailable'
}

interface ApiErrorPayload {
  code?: string
  message?: string
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    let payload: ApiErrorPayload = {}
    try {
      payload = (await response.json()) as ApiErrorPayload
    } catch {
      // The status remains enough for a controlled generic error.
    }
    throw new ApiError(response.status, payload.code ?? 'request_failed', payload.message ?? 'Request failed')
  }
  return (await response.json()) as T
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/v1/system/health')
}

export function getMediaPage(kind: MediaKind, query: CatalogQuery = {}): Promise<MediaPage> {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.sort) params.set('sort', query.sort)
  if (query.genre) params.set('genre', String(query.genre))
  if (query.year) params.set('year', String(query.year))
  return request<MediaPage>(`/api/v1/${kind === 'movie' ? 'movies' : 'series'}?${params}`)
}

export function searchMedia(kind: MediaKind, search: string, page = 1): Promise<MediaPage> {
  const params = new URLSearchParams({ q: search, page: String(page) })
  return request<MediaPage>(`/api/v1/${kind === 'movie' ? 'movies' : 'series'}/search?${params}`)
}

export function getMediaDetails(kind: MediaKind, id: number): Promise<MediaDetails> {
  return request<MediaDetails>(`/api/v1/${kind === 'movie' ? 'movies' : 'series'}/${id}`)
}

export function getGenres(kind: MediaKind): Promise<Genre[]> {
  return request<Genre[]>(`/api/v1/${kind === 'movie' ? 'movies' : 'series'}/genres`)
}

export function friendlyApiError(error: unknown): string {
  if (error instanceof ApiError && error.code === 'metadata_not_configured') {
    return 'Добавьте KADR_TMDB_ACCESS_TOKEN в .env и перезапустите API.'
  }
  if (error instanceof ApiError && error.code === 'media_not_found') {
    return 'Такой фильм или сериал не найден.'
  }
  return 'Каталог временно недоступен. Попробуйте ещё раз позже.'
}

