import { fireEvent, render, screen } from '@testing-library/vue'
import { expect, test, vi } from 'vitest'

import { getMediaPage } from '../services/api'
import type { MediaKind, MediaPage } from '../types/media'
import HomePage from './HomePage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  getMediaPage: vi.fn(),
}))

function page(kind: MediaKind, title: string): MediaPage {
  return {
    page: 1,
    total_pages: 1,
    total_results: 1,
    items: [{
      id: 11, kind, title, original_title: title, overview: '', release_date: null,
      year: null, poster_url: null, backdrop_url: null, rating: 0, popularity: 0, genre_ids: [],
    }],
  }
}

test('keeps available collections visible when one fails and lets the user retry', async () => {
  let newsAvailable = false
  vi.mocked(getMediaPage).mockImplementation(async (kind, options) => {
    if (options?.sort === 'newest') {
      if (!newsAvailable) throw new Error('TMDB unavailable')
      return page(kind, 'Новый фильм')
    }
    return page(kind, kind === 'movie' ? 'Популярный фильм' : 'Популярный сериал')
  })

  const { unmount } = render(HomePage, { global: { stubs: { RouterLink: true } } })
  expect(await screen.findByRole('heading', { name: 'Популярные фильмы' })).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'Сериалы' })).toBeTruthy()
  expect(screen.queryByRole('heading', { name: 'Новинки' })).toBeNull()

  newsAvailable = true
  await fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  expect(await screen.findByRole('heading', { name: 'Новинки' })).toBeTruthy()
  expect(screen.queryByRole('status')).toBeNull()
  unmount()
})
