import { afterEach, expect, test, vi } from 'vitest'

import { ApiError, getMediaPage, getSources } from './api'

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

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/movies?page=2&sort=rating&genre=12&year=1977',
    { headers: { Accept: 'application/json' } },
  )
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

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/media/42/sources?kind=movie&sort=resolution&order=desc',
    { headers: { Accept: 'application/json' } },
  )
})
