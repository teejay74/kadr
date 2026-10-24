import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({
  addTorrent: vi.fn(),
  getSources: vi.fn(),
  getTorrent: vi.fn(),
  getTorrentFiles: vi.fn(),
  selectTorrentFile: vi.fn(),
  startTorrent: vi.fn(),
  stopTorrent: vi.fn(),
  friendlyApiError: vi.fn(() => 'Ошибка поиска'),
}))

vi.mock('../services/api', () => api)

import SourcesPanel from './SourcesPanel.vue'

beforeEach(() => {
  api.getSources.mockReset()
  api.addTorrent.mockReset()
  api.getTorrentFiles.mockReset()
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
  api.addTorrent.mockResolvedValue({
    id: 'task-id',
    media_id: 42,
    media_kind: 'movie',
    name: 'Dune',
    state: 'stoppedDL',
    progress: 0,
    downloaded_bytes: 0,
    total_size_bytes: 100,
    download_speed_bytes: 0,
    upload_speed_bytes: 0,
    peers: 0,
    seeds: 1,
    eta_seconds: null,
    selected_file_id: null,
    selected_file_path: null,
    can_start: false,
    can_stop: false,
  })
  api.getTorrentFiles.mockResolvedValue([])
})

afterEach(cleanup)

test('searches only after user action and renders normalized release data', async () => {
  render(SourcesPanel, { props: { mediaId: 42, kind: 'movie' } })

  expect(api.getSources).not.toHaveBeenCalled()
  await fireEvent.click(screen.getByRole('button', { name: 'Найти источники' }))

  expect(await screen.findByText('Dune.2024.2160p.WEB-DL.HEVC.HDR10')).toBeTruthy()
  expect(screen.getByText('24')).toBeTruthy()
  expect(screen.getByText('2160p')).toBeTruthy()
  expect(api.getSources).toHaveBeenCalledWith(42, 'movie', 'seeders', 'desc')
})

test('adds the selected normalized source as a stopped torrent task', async () => {
  render(SourcesPanel, { props: { mediaId: 42, kind: 'movie' } })
  await fireEvent.click(screen.getByRole('button', { name: 'Найти источники' }))
  await fireEvent.click(await screen.findByRole('button', { name: 'Добавить' }))

  expect(api.addTorrent).toHaveBeenCalledWith(42, 'movie', 'release-id')
  expect(await screen.findByText('Состояние: stoppedDL · сиды 1 · пиры 0')).toBeTruthy()
})
