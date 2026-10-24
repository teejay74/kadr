import type {
  CatalogQuery,
  Genre,
  MediaDetails,
  MediaKind,
  MediaPage,
  SortOrder,
  SourceResults,
  SourceSort,
  TorrentFile,
  TorrentStatus,
} from '../types/media'

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...init, headers })
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

export function addTorrent(mediaId: number, mediaKind: MediaKind, sourceId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/media/${mediaId}/torrents`, {
    method: 'POST',
    body: JSON.stringify({ media_kind: mediaKind, source_id: sourceId }),
  })
}

export function getTorrent(taskId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}`)
}

export function getTorrentFiles(taskId: string): Promise<TorrentFile[]> {
  return request<TorrentFile[]>(`/api/v1/torrents/${taskId}/files`)
}

export function selectTorrentFile(taskId: string, fileId: number): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/selection`, {
    method: 'PUT',
    body: JSON.stringify({ file_id: fileId }),
  })
}

export function startTorrent(taskId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/start`, { method: 'POST' })
}

export function stopTorrent(taskId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/stop`, { method: 'POST' })
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

export function getSources(
  mediaId: number,
  kind: MediaKind,
  sort: SourceSort = 'seeders',
  order: SortOrder = 'desc',
): Promise<SourceResults> {
  const params = new URLSearchParams({ kind, sort, order })
  return request<SourceResults>(`/api/v1/media/${mediaId}/sources?${params}`)
}

export function friendlyApiError(error: unknown): string {
  if (error instanceof ApiError && error.code === 'metadata_not_configured') {
    return 'Добавьте KADR_TMDB_ACCESS_TOKEN в .env и перезапустите API.'
  }
  if (error instanceof ApiError && error.code === 'media_not_found') {
    return 'Такой фильм или сериал не найден.'
  }
  if (error instanceof ApiError && error.code === 'indexer_not_configured') {
    return 'Prowlarr ещё не настроен. Добавьте индексатор и API-ключ.'
  }
  if (error instanceof ApiError && error.code === 'indexer_unavailable') {
    return 'Prowlarr или один из индексаторов сейчас недоступен.'
  }
  if (error instanceof ApiError && error.code === 'torrent_not_configured') {
    return 'qBittorrent ещё не настроен. Проверьте серверные учётные данные.'
  }
  if (error instanceof ApiError && error.code === 'torrent_limit_reached') {
    return 'Достигнут лимит активных загрузок.'
  }
  if (error instanceof ApiError && error.code === 'invalid_torrent_file') {
    return error.message
  }
  if (error instanceof ApiError && error.code === 'torrent_storage_unavailable') {
    return 'Хранилище загрузок недоступно или на нём недостаточно свободного места.'
  }
  if (error instanceof ApiError && ['torrent_unavailable', 'torrent_not_found'].includes(error.code)) {
    return 'Torrent Manager временно недоступен или задача больше не существует.'
  }
  return 'Каталог временно недоступен. Попробуйте ещё раз позже.'
}

