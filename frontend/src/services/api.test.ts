import { afterEach, expect, test, vi } from 'vitest'

import {
  addTorrent,
  ApiError,
  configureTorrentPrefetch,
  deleteTorrentFile,
  getMediaPage,
  getSources,
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
