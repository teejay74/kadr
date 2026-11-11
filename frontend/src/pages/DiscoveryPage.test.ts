import { cleanup, fireEvent, render, screen, within } from '@testing-library/vue'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { ApiError, getMediaPage } from '../services/api'
import type { MediaKind, MediaPage } from '../types/media'
import DiscoveryPage from './DiscoveryPage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  getMediaPage: vi.fn(),
}))

const getPage = vi.mocked(getMediaPage)

beforeEach(() => { getPage.mockReset() })
afterEach(cleanup)

function page(kind: MediaKind, number: number, totalPages: number, ...ids: number[]): MediaPage {
  return {
    items: ids.map((id) => ({
      id,
      kind,
      title: `${kind === 'movie' ? 'Фильм' : 'Сериал'} ${id}`,
      original_title: '',
      overview: '',
      release_date: null,
      year: null,
      poster_url: null,
      backdrop_url: null,
      rating: 0,
      popularity: 0,
      genre_ids: [],
    })),
    page: number,
    total_pages: totalPages,
    total_results: totalPages * 20,
  }
}

async function openCollection(path: string): Promise<void> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/new', component: DiscoveryPage, meta: { collection: 'new' } },
      { path: '/cartoons', component: DiscoveryPage, meta: { collection: 'cartoons' } },
    ],
  })
  await router.push(path)
  render(DiscoveryPage, {
    global: { plugins: [router], stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

test('loads the next movie page on demand, keeps the series page, and hides the finished button', async () => {
  getPage.mockImplementation(async (kind, query) => {
    if (kind === 'series') return page(kind, 1, 2, 1)
    return query?.page === 2 ? page(kind, 2, 2, 1, 2) : page(kind, 1, 2, 1)
  })
  await openCollection('/new')
  const films = within(await screen.findByRole('region', { name: 'Фильмы' }))
  expect(getPage).toHaveBeenCalledTimes(2)

  await fireEvent.click(films.getByRole('button', { name: 'Показать ещё фильмы' }))

  expect(await films.findByText('Фильм 2')).toBeTruthy()
  expect(films.getAllByText('Фильм 1')).toHaveLength(1)
  expect(getPage).toHaveBeenCalledWith('movie', expect.objectContaining({
    page: 2, sort: 'newest', releasedWithinDays: 365,
  }))
  expect(getPage.mock.calls.filter(([kind]) => kind === 'series')).toHaveLength(1)
  expect(films.queryByRole('button', { name: 'Показать ещё фильмы' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Показать ещё сериалы' })).toBeTruthy()
})

test('resets pagination on filter changes and ignores an older page still loading', async () => {
  let finishOldPage!: (result: MediaPage) => void
  const oldPage = new Promise<MediaPage>((resolve) => { finishOldPage = resolve })
  getPage.mockImplementation(async (kind, query) => {
    if (kind === 'series') return page(kind, 1, 1, 1)
    if (query?.ageRating === '12+') return page(kind, 1, 1, 3)
    return query?.page === 2 ? oldPage : page(kind, 1, 2, 1)
  })
  await openCollection('/cartoons?sort=rating&age=6%2B')
  const more = await screen.findByRole('button', { name: 'Показать ещё фильмы' })
  await fireEvent.update(screen.getByLabelText('Возраст'), '12+')
  await fireEvent.click(more)
  await fireEvent.click(more)
  expect(getPage.mock.calls.filter(([, query]) => query?.page === 2)).toHaveLength(1)
  expect(getPage).toHaveBeenCalledWith('movie', expect.objectContaining({
    page: 2, sort: 'rating', genre: 16, ageRating: '6+',
  }))

  await fireEvent.click(screen.getByRole('button', { name: 'Применить' }))
  expect(await screen.findByText('Фильм 3')).toBeTruthy()
  finishOldPage(page('movie', 2, 2, 2))
  await oldPage
  await nextTick()

  expect(screen.queryByText('Фильм 1')).toBeNull()
  expect(screen.queryByText('Фильм 2')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Показать ещё фильмы' })).toBeNull()
})

test('keeps the current page visible and retries the same next page after an error', async () => {
  getPage
    .mockResolvedValueOnce(page('movie', 1, 1, 1))
    .mockResolvedValueOnce(page('series', 1, 2, 1))
    .mockRejectedValueOnce(new ApiError(502, 'metadata_unavailable', 'TMDB request failed'))
    .mockResolvedValueOnce(page('series', 2, 2, 2))
  await openCollection('/cartoons')
  const series = within(await screen.findByRole('region', { name: 'Сериалы' }))
  const more = series.getByRole('button', { name: 'Показать ещё сериалы' })
  await fireEvent.click(more)

  expect(await series.findByRole('alert')).toBeTruthy()
  expect(series.getByText('Сериал 1')).toBeTruthy()
  await fireEvent.click(more)

  expect(await series.findByText('Сериал 2')).toBeTruthy()
  expect(series.queryByRole('alert')).toBeNull()
  expect(getPage.mock.calls.slice(2)).toEqual([
    ['series', expect.objectContaining({ page: 2, genre: 16 })],
    ['series', expect.objectContaining({ page: 2, genre: 16 })],
  ])
})
