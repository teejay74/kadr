import { afterEach, expect, test, vi } from 'vitest'

import {
  addTorrent,
  ApiError,
  configureTorrentPrefetch,
  deleteTorrentFile,
  getMediaPage,
  getHistoryItem,
  getSeriesSeason,
  getSources,
  getTorrentEpisodeFiles,
  selectTorrentFile,
  startCompatiblePlayback,
} from './api'

afterEach(() => {
  vi.restoreAllMocks()
})

test('builds filtered movie catalogue query', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ items: [], page: 2, total_pages: 2, total_results: 20 }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await getMediaPage('movie', { page: 2, sort: 'rating', genre: 12, year: 1977 })

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/movies?page=2&sort=rating&genre=12&year=1977')
  expect(new Headers(init.headers).get('Accept')).toBe('application/json')
})

test('preserves structured API errors', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ code: 'metadata_not_configured', message: 'Missing token' }),
    }),
  )

  await expect(getMediaPage('series')).rejects.toEqual(
    new ApiError(503, 'metadata_not_configured', 'Missing token'),
  )
})

test('builds a source search request without provider credentials', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ media_id: 42, media_kind: 'movie', query: 'Dune 2024', items: [], total: 0 }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await getSources(42, 'movie', 'resolution', 'desc')

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/media/42/sources?kind=movie&sort=resolution&order=desc')
  expect(new Headers(init.headers).get('Accept')).toBe('application/json')
})

test('adds a season marker to a series source search', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ media_id: 42, media_kind: 'series', query: 'Show S02', items: [], total: 0 }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await getSources(42, 'series', 'seeders', 'desc', 2)

  const [path] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/media/42/sources?kind=series&sort=seeders&order=desc&season_number=2')
})

test('requests normalized episode metadata for one series season', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ series_id: 42, number: 2, episodes: [] }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await getSeriesSeason(42, 2)

  const [path] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/series/42/seasons/2')
})

test('adds a selected source without exposing its provider URL', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'task' }) })
  vi.stubGlobal('fetch', fetchMock)

  await addTorrent(42, 'movie', 'a'.repeat(24))

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/media/42/torrents')
  expect(init.method).toBe('POST')
  expect(JSON.parse(String(init.body))).toEqual({ media_kind: 'movie', source_id: 'a'.repeat(24) })
  expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
})

test('keeps the season number when adding a seasonal source', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'task' }) })
  vi.stubGlobal('fetch', fetchMock)

  await addTorrent(42, 'series', 'a'.repeat(24), 2)

  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(JSON.parse(String(init.body))).toEqual({
    media_kind: 'series',
    source_id: 'a'.repeat(24),
    season_number: 2,
  })
})

test('replaces the episode prefetch queue with explicit file ids', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'task' }) })
  vi.stubGlobal('fetch', fetchMock)

  await configureTorrentPrefetch('task', [2, 3, 4])

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/torrents/task/prefetch')
  expect(init.method).toBe('PUT')
  expect(JSON.parse(String(init.body))).toEqual({ file_ids: [2, 3, 4] })
})

test('binds a selected torrent file to catalogue episode identity', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'task' }) })
  vi.stubGlobal('fetch', fetchMock)

  await selectTorrentFile('task', 7, {
    id: 1003,
    season_number: 2,
    number: 3,
    name: 'Episode 3',
    overview: '',
    air_date: null,
    runtime_minutes: 45,
    still_url: null,
    rating: 0,
  })

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/torrents/task/selection')
  expect(JSON.parse(String(init.body))).toEqual({
    file_id: 7,
    season_number: 2,
    episode_number: 3,
    catalog_episode_id: 1003,
  })
})

test('requests persisted episode-to-file bindings for a torrent task', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] })
  vi.stubGlobal('fetch', fetchMock)

  await getTorrentEpisodeFiles('task/id')

  const [path] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/torrents/task/id/episode-files')
})

test('requests history for one episode independently', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => null })
  vi.stubGlobal('fetch', fetchMock)

  await getHistoryItem(42, 'series', {
    id: 1003,
    season_number: 2,
    number: 3,
    name: 'Episode 3',
    overview: '',
    air_date: null,
    runtime_minutes: 45,
    still_url: null,
    rating: 0,
  })

  const [path] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/history/42?media_kind=series&season_number=2&episode_number=3')
})

test('deletes one downloaded torrent file without deleting the release', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ task_id: 'task', file_id: 3, reclaimed_bytes: 100 }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await deleteTorrentFile('task', 3)

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/torrents/task/files/3')
  expect(init.method).toBe('DELETE')
})

test('requests the audio-only FFmpeg preparation mode explicitly', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ mode: 'audio_only', state: 'processing', progress: 0.1 }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await startCompatiblePlayback('task/id', 'audio_only')

  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(path).toBe('/api/v1/torrents/task%2Fid/compatible?mode=audio_only')
  expect(init.method).toBe('POST')
})
