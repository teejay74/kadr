import { render, screen } from '@testing-library/vue'
import { afterEach, expect, test, vi } from 'vitest'

import HomePage from './HomePage.vue'

afterEach(() => {
  vi.restoreAllMocks()
})

test('shows real API readiness details', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        service: 'kadr-api',
        version: '0.1.0',
        database: 'ok',
      }),
    }),
  )

  render(HomePage)

  expect(await screen.findByText(/SQLite подключена/)).toBeTruthy()
})

test('shows a controlled error when API is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

  render(HomePage)

  expect(await screen.findByText('API пока недоступен')).toBeTruthy()
})

