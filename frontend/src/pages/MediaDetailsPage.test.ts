import { fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, expect, test, vi } from 'vitest'

import * as api from '../services/api'
import MediaDetailsPage from './MediaDetailsPage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  getFavorites: vi.fn(),
  getMediaDetails: vi.fn(),
  getSeriesSeason: vi.fn(),
}))

const details = {
  id: 42,
  kind: 'series' as const,
  title: 'Тестовый сериал',
  original_title: 'Test Series',
  overview: 'Описание сериала.',
  release_date: '2024-01-01',
  year: 2024,
  poster_url: null,
  backdrop_url: null,
  rating: 8.1,
  popularity: 10,
  genre_ids: [18],
  genres: [{ id: 18, name: 'Драма' }],
  runtime_minutes: 50,
  status: 'Returning Series',
  tagline: null,
  cast: [],
  trailer_url: null,
  seasons: [
    { id: 1, number: 1, name: 'Сезон 1', episode_count: 1, air_date: null, poster_url: null },
    { id: 2, number: 2, name: 'Сезон 2', episode_count: 1, air_date: null, poster_url: null },
  ],
  season_count: 2,
  episode_count: 2,
}

function season(number: number) {
  return {
    id: number,
    series_id: 42,
    number,
    name: `Сезон ${number}`,
    overview: '',
    air_date: null,
    poster_url: null,
    episodes: [{
      id: 600 + number,
      season_number: number,
      number: 1,
      name: `Эпизод сезона ${number}`,
      overview: '',
      air_date: null,
      runtime_minutes: 50,
      still_url: null,
      rating: 0,
    }],
  }
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(api.getMediaDetails).mockResolvedValue(details)
  vi.mocked(api.getFavorites).mockResolvedValue([])
  vi.mocked(api.getSeriesSeason).mockImplementation(async (_id, number) => season(number))
})

test('restores the last season and reloads episodes after season selection', async () => {
  localStorage.setItem('kadr:season:42', '2')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/series/:id', component: MediaDetailsPage, meta: { kind: 'series' } }],
  })
  await router.push('/series/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: { SourcesPanel: { template: '<section id="media-sources">Legacy sources</section>' } },
    },
  })

  expect(await screen.findByText('Эпизод сезона 2')).toBeTruthy()
  expect(api.getSeriesSeason).toHaveBeenCalledWith(42, 2)

  await fireEvent.update(screen.getByLabelText('Сезон'), '1')
  await waitFor(() => expect(api.getSeriesSeason).toHaveBeenCalledWith(42, 1))
  expect(await screen.findByText('Эпизод сезона 1')).toBeTruthy()
  expect(localStorage.getItem('kadr:season:42')).toBe('1')
})
