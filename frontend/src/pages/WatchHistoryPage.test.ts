import { cleanup, fireEvent, render, screen, within } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, expect, test, vi } from 'vitest'

import { getHistory } from '../services/api'
import type { HistoryItem } from '../types/media'
import WatchHistoryPage from './WatchHistoryPage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  getHistory: vi.fn(),
}))

const movie: HistoryItem = {
  id: 'movie',
  media_id: 42,
  media_kind: 'movie',
  profile_key: 'default',
  season_number: null,
  episode_number: null,
  catalog_episode_id: null,
  episode: null,
  title: 'Фильм из истории',
  poster_url: null,
  position_seconds: 600,
  duration_seconds: 3600,
  completed: false,
  updated_at: '2026-11-12T15:00:00',
}
const episode: HistoryItem = {
  ...movie,
  id: 'episode',
  media_kind: 'series',
  title: 'Сериал из истории',
  season_number: 2,
  episode_number: 3,
  updated_at: '2026-11-13T15:00:00',
}

async function renderPage(): Promise<void> {
  const placeholder = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/history', component: WatchHistoryPage },
      { path: '/movies/:id', name: 'movie-details', component: placeholder },
      { path: '/series/:id', name: 'series-details', component: placeholder },
    ],
  })
  await router.push('/history')
  render(WatchHistoryPage, { global: { plugins: [router] } })
}

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

test('shows recent records with progress, completion, and exact resume links', async () => {
  vi.mocked(getHistory).mockResolvedValue([
    episode,
    movie,
    {
      ...episode, id: 'completed', episode_number: 2, completed: true, position_seconds: 0,
      updated_at: '2026-11-11T15:00:00',
    },
    {
      ...episode, id: 'legacy', title: 'Старая запись', season_number: null, episode_number: null,
      updated_at: '2026-11-10T15:00:00',
    },
  ])
  await renderPage()

  const rows = await screen.findAllByRole('listitem')
  expect(rows).toHaveLength(4)
  const [first, second, completed, legacy] = rows.map((row) => within(row))
  expect(first!.getByText('Сезон 2 · Серия 3')).toBeTruthy()
  expect(first!.getByText('10:00 / 1:00:00')).toBeTruthy()
  expect(first!.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('17')
  expect(first!.getByRole('link', { name: 'Продолжить' }).getAttribute('href'))
    .toBe('/series/42?season=2&episode=3&resume=1')
  expect(second!.getByRole('link', { name: 'Продолжить' }).getAttribute('href'))
    .toBe('/movies/42?resume=1')
  expect(completed!.getByText('Просмотрено')).toBeTruthy()
  expect(completed!.queryByRole('link', { name: 'Продолжить' })).toBeNull()
  expect(legacy!.getByRole('link', { name: 'Выбрать эпизод' }).getAttribute('href')).toBe('/series/42')

  await fireEvent.click(screen.getByRole('button', { name: 'Просмотрено' }))
  expect(within(screen.getByRole('listitem')).getByText('Сезон 2 · Серия 2')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'В процессе' }))
  expect(screen.getAllByRole('listitem')).toHaveLength(3)
  expect(screen.queryByText('Сезон 2 · Серия 2')).toBeNull()
})

test('allows retry after a failed request and shows the empty state', async () => {
  vi.mocked(getHistory).mockRejectedValueOnce(new Error('Сеть недоступна')).mockResolvedValueOnce([])
  await renderPage()

  expect(await screen.findByText('Журнал недоступен')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  expect(await screen.findByText('Журнал пока пуст')).toBeTruthy()
})
