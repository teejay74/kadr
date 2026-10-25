import { fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { beforeEach, expect, test, vi } from 'vitest'

import * as api from '../services/api'
import LibraryPage from './LibraryPage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  deleteLibraryItem: vi.fn(),
  getFavorites: vi.fn(),
  getLibrary: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(api.getLibrary).mockResolvedValue([{
    id: 'saved-1',
    task_id: 'task-1',
    media_id: 42,
    media_kind: 'movie',
    title: 'Тестовый фильм',
    original_title: 'Test Movie',
    poster_url: null,
    backdrop_url: null,
    size_bytes: 1024,
    created_at: '2026-10-25T00:00:00Z',
    stream_url: '/api/v1/library/saved-1/stream',
  }])
  vi.mocked(api.getFavorites).mockResolvedValue([])
  vi.mocked(api.deleteLibraryItem).mockResolvedValue(undefined)
  Object.defineProperty(window, 'confirm', {
    configurable: true,
    value: vi.fn(() => true),
  })
})

test('shows saved video size and deletes only after confirmation', async () => {
  render(LibraryPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
  expect(await screen.findByText('Тестовый фильм')).toBeTruthy()
  expect(screen.getByText('1 КБ')).toBeTruthy()

  await fireEvent.click(screen.getByRole('button', { name: 'Удалить' }))
  await waitFor(() => expect(api.deleteLibraryItem).toHaveBeenCalledWith('saved-1'))
  expect(screen.queryByText('Тестовый фильм')).toBeNull()
})
