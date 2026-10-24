import { fireEvent, render, screen } from '@testing-library/vue'
import { beforeEach, expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getSources: vi.fn(),
  friendlyApiError: vi.fn(() => 'Ошибка поиска'),
}))

vi.mock('../services/api', () => api)

import SourcesPanel from './SourcesPanel.vue'

beforeEach(() => {
  api.getSources.mockReset()
  api.getSources.mockResolvedValue({
    media_id: 42,
    media_kind: 'movie',
    query: 'Dune 2024',
    total: 1,
    items: [
      {
        id: 'release-id',
        title: 'Dune.2024.2160p.WEB-DL.HEVC.HDR10',
        indexer: 'Example Indexer',
        size_bytes: 10_737_418_240,
        seeders: 24,
        peers: 3,
        published_at: null,
        protocol: 'torrent',
        resolution: '2160p',
        source: 'WEB-DL',
        codec: 'HEVC',
        hdr: true,
        hdr_format: 'HDR10',
        audio: null,
        language: null,
        release_type: 'web',
      },
    ],
  })
})

test('searches only after user action and renders normalized release data', async () => {
  render(SourcesPanel, { props: { mediaId: 42, kind: 'movie' } })

  expect(api.getSources).not.toHaveBeenCalled()
  await fireEvent.click(screen.getByRole('button', { name: 'Найти источники' }))

  expect(await screen.findByText('Dune.2024.2160p.WEB-DL.HEVC.HDR10')).toBeTruthy()
  expect(screen.getByText('24')).toBeTruthy()
  expect(screen.getByText('2160p')).toBeTruthy()
  expect(api.getSources).toHaveBeenCalledWith(42, 'movie', 'seeders', 'desc')
})
