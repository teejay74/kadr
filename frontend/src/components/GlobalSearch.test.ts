import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, expect, test, vi } from 'vitest'

import { searchMedia } from '../services/api'
import type { MediaCardData, MediaPage } from '../types/media'
import GlobalSearch from './GlobalSearch.vue'

vi.mock('../services/api', () => ({ searchMedia: vi.fn() }))

const movie: MediaCardData = {
  id: 42,
  kind: 'movie',
  title: 'Чужие',
  original_title: 'Aliens',
  overview: '',
  release_date: '1986-01-01',
  year: 1986,
  poster_url: null,
  backdrop_url: null,
  rating: 8,
  popularity: 10,
  genre_ids: [],
}

function page(items: MediaCardData[]): MediaPage {
  return { items, page: 1, total_pages: 1, total_results: items.length }
}

async function setup() {
  const component = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component },
      { path: '/search', name: 'search', component },
      { path: '/movies/:id', name: 'movie-details', component },
      { path: '/series/:id', name: 'series-details', component },
    ],
  })
  await router.push('/')
  render(GlobalSearch, { global: { plugins: [router] } })
  return { router, input: screen.getByRole('combobox', { name: 'Поиск фильмов и сериалов' }) }
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.resetAllMocks()
})

test('debounces film and series suggestions, highlights a match, and opens a selected result', async () => {
  const series = { ...movie, id: 43, kind: 'series' as const, title: 'Чужестранка', original_title: 'Outlander', year: 2014 }
  vi.mocked(searchMedia).mockImplementation(async (kind) => page([kind === 'movie' ? movie : series]))
  const { router, input } = await setup()
  await fireEvent.update(input, 'ч')
  await fireEvent.update(input, 'чу')
  await fireEvent.update(input, 'чуж')
  expect(searchMedia).not.toHaveBeenCalled()

  const options = await screen.findAllByRole('option')
  expect(searchMedia).toHaveBeenCalledTimes(2)
  expect(options[0]?.textContent).toContain('Чужие / Aliens (1986)')
  expect(options[0]?.querySelector('mark')?.textContent).toBe('Чуж')
  expect(options[1]?.textContent).toContain('Чужестранка / Outlander (2014)')
  await fireEvent.keyDown(input, { key: 'ArrowDown' })
  await fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(options[1]?.getAttribute('aria-selected')).toBe('true')
  await fireEvent.submit(screen.getByRole('search'))
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/series/43'))
  expect(screen.queryByRole('listbox')).toBeNull()
})

test('aborts stale requests and leaves Enter available for the full results page', async () => {
  vi.useFakeTimers()
  let finishOld!: (value: MediaPage) => void
  const oldResponse = new Promise<MediaPage>((resolve) => { finishOld = resolve })
  vi.mocked(searchMedia).mockImplementation((_kind, query) => (
    query === 'чуж' ? oldResponse : Promise.resolve(page([]))
  ))
  const { router, input } = await setup()
  await fireEvent.update(input, 'чуж')
  await vi.advanceTimersByTimeAsync(400)
  const oldSignal = vi.mocked(searchMedia).mock.calls[0]?.[3]
  await fireEvent.update(input, 'дюна')
  expect(oldSignal?.aborted).toBe(true)
  await vi.advanceTimersByTimeAsync(400)
  finishOld(page([movie]))
  await vi.advanceTimersByTimeAsync(0)
  expect(screen.queryByRole('option')).toBeNull()
  expect(screen.getByText('Совпадений нет')).toBeTruthy()
  await fireEvent.keyDown(input, { key: 'Escape' })
  expect(screen.queryByRole('listbox')).toBeNull()
  await fireEvent.submit(screen.getByRole('search'))
  await vi.waitFor(() => expect(router.currentRoute.value.query.q).toBe('дюна'))
})
