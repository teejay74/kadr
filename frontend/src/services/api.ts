import type {
  CatalogQuery,
  CacheFileDeletion,
  EpisodeFileBinding,
  EpisodeSummary,
  Genre,
  FavoriteItem,
  HistoryItem,
  LibraryItem,
  MediaSnapshot,
  MediaDetails,
  MediaKind,
  MediaPage,
  SeasonDetails,
  PlaybackPreparation,
  PlaybackMode,
  SortOrder,
  StreamReadiness,
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
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function getLibrary(): Promise<LibraryItem[]> {
  return request<LibraryItem[]>('/api/v1/library')
}

export function saveToLibrary(taskId: string, media: MediaSnapshot): Promise<LibraryItem> {
  return saveEpisodeToLibrary(taskId, media)
}

export function saveEpisodeToLibrary(
  taskId: string,
  media: MediaSnapshot,
  episode?: EpisodeSummary | null,
): Promise<LibraryItem> {
  return request<LibraryItem>('/api/v1/library', {
    method: 'POST',
    body: JSON.stringify({
      task_id: taskId,
      ...media,
      ...(episode ? {
        season_number: episode.season_number,
        episode_number: episode.number,
        catalog_episode_id: episode.id,
      } : {}),
    }),
  })
}

export function deleteLibraryItem(itemId: string): Promise<void> {
  return request<void>(`/api/v1/library/${encodeURIComponent(itemId)}`, { method: 'DELETE' })
}

export function getFavorites(): Promise<FavoriteItem[]> {
  return request<FavoriteItem[]>('/api/v1/favorites')
}

export function addFavorite(media: MediaSnapshot): Promise<FavoriteItem> {
  return request<FavoriteItem>('/api/v1/favorites', {
    method: 'POST',
    body: JSON.stringify(media),
  })
}

export function deleteFavorite(kind: MediaKind, mediaId: number): Promise<void> {
  return request<void>(`/api/v1/favorites/${kind}/${mediaId}`, { method: 'DELETE' })
}

export function getHistoryItem(
  mediaId: number,
  kind: MediaKind,
  episode?: EpisodeSummary | null,
): Promise<HistoryItem | null> {
  const params = new URLSearchParams({ media_kind: kind })
  if (episode) {
    params.set('season_number', String(episode.season_number))
    params.set('episode_number', String(episode.number))
  }
  return request<HistoryItem | null>(`/api/v1/history/${mediaId}?${params}`)
}

export type HistoryUpdatePayload = Pick<
  HistoryItem,
  'media_kind' | 'title' | 'poster_url' | 'position_seconds' | 'duration_seconds' | 'completed'
> & Partial<Pick<
  HistoryItem,
  'profile_key' | 'season_number' | 'episode_number' | 'catalog_episode_id'
>>

export function updateHistory(
  mediaId: number,
  payload: HistoryUpdatePayload,
): Promise<HistoryItem> {
  return request<HistoryItem>(`/api/v1/history/${mediaId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function addTorrent(
  mediaId: number,
  mediaKind: MediaKind,
  sourceId: string,
  seasonNumber?: number | null,
): Promise<TorrentStatus> {
  const body: { media_kind: MediaKind, source_id: string, season_number?: number } = {
    media_kind: mediaKind,
    source_id: sourceId,
  }
  if (seasonNumber !== null && seasonNumber !== undefined) body.season_number = seasonNumber
  return request<TorrentStatus>(`/api/v1/media/${mediaId}/torrents`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getTorrent(taskId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}`)
}

export function getMediaTorrent(mediaId: number, mediaKind: MediaKind): Promise<TorrentStatus> {
  const params = new URLSearchParams({ media_kind: mediaKind })
  return request<TorrentStatus>(`/api/v1/media/${mediaId}/torrents?${params}`)
}

export function getTorrentFiles(taskId: string): Promise<TorrentFile[]> {
  return request<TorrentFile[]>(`/api/v1/torrents/${taskId}/files`)
}

export function getTorrentEpisodeFiles(taskId: string): Promise<EpisodeFileBinding[]> {
  return request<EpisodeFileBinding[]>(`/api/v1/torrents/${taskId}/episode-files`)
}

export function deleteTorrentFile(taskId: string, fileId: number): Promise<CacheFileDeletion> {
  return request<CacheFileDeletion>(
    `/api/v1/torrents/${encodeURIComponent(taskId)}/files/${fileId}`,
    { method: 'DELETE' },
  )
}

export function selectTorrentFile(
  taskId: string,
  fileId: number,
  episode?: EpisodeSummary | null,
): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/selection`, {
    method: 'PUT',
    body: JSON.stringify({
      file_id: fileId,
      ...(episode ? {
        season_number: episode.season_number,
        episode_number: episode.number,
        catalog_episode_id: episode.id,
      } : {}),
    }),
  })
}

export function configureTorrentPrefetch(
  taskId: string,
  fileIds: number[],
): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/prefetch`, {
    method: 'PUT',
    body: JSON.stringify({ file_ids: fileIds }),
  })
}

export function startTorrent(taskId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/start`, { method: 'POST' })
}

export function stopTorrent(taskId: string): Promise<TorrentStatus> {
  return request<TorrentStatus>(`/api/v1/torrents/${taskId}/stop`, { method: 'POST' })
}

export function getStreamReadiness(taskId: string): Promise<StreamReadiness> {
  return request<StreamReadiness>(`/api/v1/torrents/${encodeURIComponent(taskId)}/stream/readiness`)
}

export function startCompatiblePlayback(
  taskId: string,
  mode: PlaybackMode = 'compatible',
): Promise<PlaybackPreparation> {
  const query = mode === 'audio_only' ? '?mode=audio_only' : ''
  return request<PlaybackPreparation>(`/api/v1/torrents/${encodeURIComponent(taskId)}/compatible${query}`, {
    method: 'POST',
  })
}

export function getCompatiblePlayback(
  taskId: string,
  mode: PlaybackMode = 'compatible',
): Promise<PlaybackPreparation> {
  const query = mode === 'audio_only' ? '?mode=audio_only' : ''
  return request<PlaybackPreparation>(
    `/api/v1/torrents/${encodeURIComponent(taskId)}/compatible${query}`,
  )
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

export function getSeriesSeason(seriesId: number, seasonNumber: number): Promise<SeasonDetails> {
  return request<SeasonDetails>(`/api/v1/series/${seriesId}/seasons/${seasonNumber}`)
}

export function getGenres(kind: MediaKind): Promise<Genre[]> {
  return request<Genre[]>(`/api/v1/${kind === 'movie' ? 'movies' : 'series'}/genres`)
}

export function getSources(
  mediaId: number,
  kind: MediaKind,
  sort: SourceSort = 'seeders',
  order: SortOrder = 'desc',
  seasonNumber?: number,
): Promise<SourceResults> {
  const params = new URLSearchParams({ kind, sort, order })
  if (seasonNumber !== undefined) params.set('season_number', String(seasonNumber))
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
  if (error instanceof ApiError && error.code === 'playback_preparation_failed') {
    return error.message
  }
  if (error instanceof ApiError && error.code === 'playback_preparation_limit') {
    return 'Уже подготавливается другая совместимая версия. Дождитесь её завершения.'
  }
  if (error instanceof ApiError && error.code === 'library_conflict') {
    return error.message
  }
  if (error instanceof ApiError && error.code === 'library_storage') {
    return 'Хранилище библиотеки недоступно. Проверьте каталог и свободное место.'
  }
  if (error instanceof ApiError && error.code === 'library_not_found') {
    return 'Запись библиотеки не найдена.'
  }
  if (error instanceof ApiError && error.code === 'cache_delete_conflict') {
    return 'Этот файл сейчас нельзя удалить: закройте просмотр, дождитесь подготовки видео или удалите его из библиотеки.'
  }
  if (error instanceof ApiError && error.code === 'cache_file_not_found') {
    return 'Скачанный файл уже удалён или недоступен.'
  }
  if (error instanceof ApiError && error.code === 'cache_storage_error') {
    return 'Не удалось безопасно удалить файл из хранилища KADR.'
  }
  return 'Каталог временно недоступен. Попробуйте ещё раз позже.'
}

