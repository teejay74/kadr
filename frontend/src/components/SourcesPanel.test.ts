import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({
  addTorrent: vi.fn(),
  configureTorrentPrefetch: vi.fn(),
  deleteTorrentFile: vi.fn(),
  getSources: vi.fn(),
  getMediaTorrent: vi.fn(),
  getTorrent: vi.fn(),
  getTorrentFiles: vi.fn(),
  selectTorrentFile: vi.fn(),
  startTorrent: vi.fn(),
  stopTorrent: vi.fn(),
  friendlyApiError: vi.fn(() => 'Ошибка поиска'),
}))

vi.mock('../services/api', () => api)

import SourcesPanel from './SourcesPanel.vue'

const stoppedTorrent = {
  id: 'task-id',
  media_id: 42,
  media_kind: 'movie' as const,
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
}

beforeEach(() => {
  localStorage.clear()
  for (const mock of Object.values(api)) mock.mockReset()
  api.friendlyApiError.mockReturnValue('Ошибка поиска')
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
  api.addTorrent.mockResolvedValue(stoppedTorrent)
  api.getMediaTorrent.mockRejectedValue(new Error('No current task'))
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
  await fireEvent.click(await screen.findByRole('button', { name: 'Выбрать релиз' }))

  expect(api.addTorrent).toHaveBeenCalledWith(42, 'movie', 'release-id')
  expect(await screen.findByText('Получаем список файлов…')).toBeTruthy()

  expect(screen.queryByRole('button', { name: 'Выбрать релиз' })).toBeNull()
  expect(localStorage.getItem('kadr:torrent:movie:42')).toBe('task-id')
  const changeButton = screen.getByRole('button', {
    name: 'Сменить релиз',
  }) as HTMLButtonElement
  await vi.waitFor(() => expect(changeButton.disabled).toBe(false))
  await fireEvent.click(changeButton)
  await vi.waitFor(() => {
    expect(
      (screen.getByRole('button', { name: 'Выбрать релиз' }) as HTMLButtonElement).disabled,
    ).toBe(false)
  })
  expect(localStorage.getItem('kadr:torrent:movie:42')).toBe('dismissed')
})

test('uses one clear action to select a video and start its download', async () => {
  api.getTorrentFiles.mockResolvedValue([
    {
      id: 0,
      name: 'Season/poster.jpg',
      size_bytes: 10,
      progress: 0,
      priority: 0,
      is_video: false,
    },
    {
      id: 1,
      name: 'Season/S01E01.mkv',
      size_bytes: 1_000,
      progress: 0,
      priority: 0,
      is_video: true,
    },
  ])
  api.selectTorrentFile.mockResolvedValue({
    ...stoppedTorrent,
    selected_file_id: 1,
    selected_file_path: 'Season/S01E01.mkv',
    can_start: true,
  })
  api.startTorrent.mockResolvedValue({
    ...stoppedTorrent,
    state: 'downloading',
    selected_file_id: 1,
    selected_file_path: 'Season/S01E01.mkv',
    can_stop: true,
  })

  render(SourcesPanel, { props: { mediaId: 42, kind: 'movie' } })
  await fireEvent.click(screen.getByRole('button', { name: 'Найти источники' }))
  await fireEvent.click(await screen.findByRole('button', { name: 'Выбрать релиз' }))
  await fireEvent.click(await screen.findByRole('button', { name: /Выбрать и скачать/ }))

  expect(api.selectTorrentFile).toHaveBeenCalledWith('task-id', 1)
  expect(api.startTorrent).toHaveBeenCalledWith('task-id')
  expect(await screen.findByRole('button', { name: 'Начать просмотр' })).toBeTruthy()
  expect(screen.getByText('Выбрано для просмотра')).toBeTruthy()
  expect(screen.getAllByText('Сезон 1 · Серия 1')).toHaveLength(2)
  expect(screen.getAllByText('Season/S01E01.mkv')).toHaveLength(2)
  expect(screen.queryByText('Скрыто сопутствующих файлов: 1.')).toBeNull()
})

test('recognizes the alternate season and episode filename format', async () => {
  api.getMediaTorrent.mockResolvedValue({
    ...stoppedTorrent,
    media_kind: 'series',
    selected_file_id: 7,
    selected_file_path: 'Series/1x07.mp4',
  })
  api.getTorrentFiles.mockResolvedValue([
    {
      id: 7,
      name: 'Series/1x07.mp4',
      size_bytes: 2_000,
      progress: 1,
      priority: 1,
      is_video: true,
    },
  ])

  render(SourcesPanel, { props: { mediaId: 42, kind: 'series', title: 'Series' } })

  expect((await screen.findAllByText('Сезон 1 · Серия 7')).length).toBeGreaterThan(0)
})

test('queues several following episodes without changing the selected episode', async () => {
  const selectedTorrent = {
    ...stoppedTorrent,
    media_kind: 'series' as const,
    progress: 1,
    selected_file_id: 0,
    selected_file_path: 'Series/S01E01.mkv',
  }
  const files = [
    {
      id: 0,
      name: 'Series/S01E01.mkv',
      size_bytes: 1_000,
      progress: 1,
      priority: 1,
      is_video: true,
    },
    {
      id: 1,
      name: 'Series/S01E02.mkv',
      size_bytes: 1_000,
      progress: 0,
      priority: 0,
      is_video: true,
    },
    {
      id: 2,
      name: 'Series/S01E03.mkv',
      size_bytes: 1_000,
      progress: 0,
      priority: 0,
      is_video: true,
    },
  ]
  api.getMediaTorrent.mockResolvedValue(selectedTorrent)
  api.getTorrentFiles
    .mockResolvedValueOnce(files)
    .mockResolvedValueOnce(files.map((file) => (
      file.id === 0 ? file : { ...file, priority: 1 }
    )))
    .mockResolvedValueOnce(files)
  api.configureTorrentPrefetch.mockResolvedValue({
    ...selectedTorrent,
    state: 'downloading',
    progress: 0.4,
    can_stop: true,
  })

  render(SourcesPanel, { props: { mediaId: 42, kind: 'series', title: 'Series' } })

  await fireEvent.click(await screen.findByRole('button', { name: 'Скачать следующие 2' }))
  expect(api.configureTorrentPrefetch).toHaveBeenCalledWith('task-id', [1, 2])
  expect(await screen.findByText('Загружаются заранее')).toBeTruthy()
  expect(screen.getByText('Сезон 1 · Серия 2')).toBeTruthy()
  expect(screen.getByText('Сезон 1 · Серия 3')).toBeTruthy()

  await fireEvent.click(screen.getByRole('button', {
    name: 'Отменить загрузку следующих серий',
  }))
  expect(api.configureTorrentPrefetch).toHaveBeenLastCalledWith('task-id', [])
})

test('requires confirmation and deletes one downloaded episode', async () => {
  api.getMediaTorrent.mockResolvedValue({
    ...stoppedTorrent,
    media_kind: 'series',
    progress: 1,
    selected_file_id: 3,
    selected_file_path: 'Series/S01E03.mkv',
  })
  api.getTorrentFiles.mockResolvedValue([
    {
      id: 3,
      name: 'Series/S01E03.mkv',
      size_bytes: 2_048,
      progress: 1,
      priority: 1,
      is_video: true,
    },
  ])
  api.deleteTorrentFile.mockResolvedValue({
    task_id: 'task-id',
    file_id: 3,
    reclaimed_bytes: 2_048,
    selected_file_cleared: true,
  })

  render(SourcesPanel, { props: { mediaId: 42, kind: 'series', title: 'Series' } })

  await fireEvent.click(await screen.findByRole('button', { name: 'Удалить файл' }))
  expect(api.deleteTorrentFile).not.toHaveBeenCalled()
  await fireEvent.click(screen.getByRole('button', { name: 'Да, удалить' }))

  expect(api.deleteTorrentFile).toHaveBeenCalledWith('task-id', 3)
  expect(await screen.findByText('Сезон 1 · Серия 3 удалён. Освобождено 2 КБ.')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Начать просмотр' })).toBeNull()
})

test('restores the current media task after a page reload', async () => {
  localStorage.setItem('kadr:torrent:movie:42', 'task-id')
  api.getTorrent.mockResolvedValue({
    ...stoppedTorrent,
    state: 'downloading',
    selected_file_id: 1,
    selected_file_path: 'Season/S01E01.mkv',
    can_stop: true,
  })
  api.getTorrentFiles.mockResolvedValue([
    {
      id: 1,
      name: 'Season/S01E01.mkv',
      size_bytes: 1_000,
      progress: 0.4,
      priority: 1,
      is_video: true,
    },
  ])

  render(SourcesPanel, { props: { mediaId: 42, kind: 'movie' } })

  expect(await screen.findByText('Загружаем видео')).toBeTruthy()
  expect(api.getTorrent).toHaveBeenCalledWith('task-id')
  expect(screen.queryByRole('button', { name: 'Найти источники' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Начать просмотр' })).toBeTruthy()
})

test('finds the latest server task when this browser has not stored its id', async () => {
  api.getMediaTorrent.mockResolvedValue({
    ...stoppedTorrent,
    state: 'downloading',
    selected_file_id: 1,
    selected_file_path: 'Season/S01E01.mkv',
    can_stop: true,
  })
  api.getTorrentFiles.mockResolvedValue([
    {
      id: 1,
      name: 'Season/S01E01.mkv',
      size_bytes: 1_000,
      progress: 0.4,
      priority: 1,
      is_video: true,
    },
  ])

  render(SourcesPanel, { props: { mediaId: 42, kind: 'movie' } })

  expect(await screen.findByText('Загружаем видео')).toBeTruthy()
  expect(api.getMediaTorrent).toHaveBeenCalledWith(42, 'movie')
  expect(localStorage.getItem('kadr:torrent:movie:42')).toBe('task-id')
})
