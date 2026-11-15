import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import * as api from '../services/api'
import DownloadsPage from './DownloadsPage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  deleteTorrent: vi.fn(),
  deleteTorrentFile: vi.fn(),
  getTorrentFiles: vi.fn(),
  getTorrents: vi.fn(),
  queueTorrentFiles: vi.fn(),
  startTorrent: vi.fn(),
  stopTorrent: vi.fn(),
}))

const task = {
  id: 'task-id',
  media_id: 42,
  media_kind: 'series' as const,
  name: 'Series S01 1080p',
  state: 'downloading',
  progress: 0.4,
  downloaded_bytes: 400,
  total_size_bytes: 1000,
  download_speed_bytes: 100,
  upload_speed_bytes: 0,
  peers: 2,
  seeds: 4,
  eta_seconds: 60,
  selected_file_id: 1,
  selected_file_path: 'Series.S01E01.mkv',
  can_start: false,
  can_stop: true,
}

beforeEach(() => {
  vi.mocked(api.getTorrents).mockResolvedValue([task])
  vi.mocked(api.getTorrentFiles).mockResolvedValue([{
    id: 1,
    name: 'Series.S01E01.mkv',
    size_bytes: 1000,
    progress: 1,
    priority: 1,
    is_video: true,
    duration_seconds: null,
  }])
  vi.mocked(api.stopTorrent).mockResolvedValue({
    ...task,
    state: 'stoppedDL',
    can_start: true,
    can_stop: false,
  })
  vi.mocked(api.deleteTorrentFile).mockResolvedValue({
    task_id: task.id,
    file_id: 1,
    reclaimed_bytes: 1000,
    selected_file_cleared: true,
  })
  vi.mocked(api.deleteTorrent).mockResolvedValue({
    task_id: task.id,
    reclaimed_bytes: 400,
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllTimers()
  vi.useRealTimers()
})

test('shows technical status and controls away from the media page', async () => {
  render(DownloadsPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })

  expect(await screen.findByText('Series S01 1080p')).toBeTruthy()
  expect(screen.getByText('40%')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Приостановить' }))

  await waitFor(() => expect(api.stopTorrent).toHaveBeenCalledWith('task-id'))
  expect(await screen.findByRole('button', { name: 'Продолжить' })).toBeTruthy()
})

test('loads files on demand and requires a second click before deletion', async () => {
  render(DownloadsPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })

  await fireEvent.click(await screen.findByRole('button', { name: 'Показать файлы' }))
  expect(await screen.findByText('Series.S01E01.mkv', { selector: 'strong' })).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Удалить файл' }))

  expect(api.deleteTorrentFile).not.toHaveBeenCalled()
  await fireEvent.click(screen.getByRole('button', { name: 'Подтвердить удаление' }))
  await waitFor(() => expect(api.deleteTorrentFile).toHaveBeenCalledWith('task-id', 1))
})

test('requires explicit confirmation before deleting a whole download', async () => {
  render(DownloadsPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })

  await fireEvent.click(await screen.findByRole('button', { name: 'Удалить загрузку' }))

  expect(api.deleteTorrent).not.toHaveBeenCalled()
  expect(screen.getByRole('alert').textContent).toMatch(/все её загруженные файлы будут удалены/)
  await fireEvent.click(screen.getByRole('button', { name: /Подтвердить удаление/ }))
  await waitFor(() => expect(api.deleteTorrent).toHaveBeenCalledWith('task-id'))
  expect(screen.queryByText('Series S01 1080p')).toBeNull()
})

test('queues one skipped episode and then the remaining videos', async () => {
  const episode = {
    size_bytes: 1000,
    priority: 0,
    is_video: true,
    duration_seconds: null,
  }
  const next = { ...episode, id: 2, name: 'Series.S01E02.mkv', progress: 0.18 }
  const last = { ...episode, id: 3, name: 'Series.S01E03.mkv', progress: 0 }
  const extra = { ...episode, id: 4, name: 'readme.txt', is_video: false, progress: 0 }
  vi.mocked(api.getTorrentFiles)
    .mockResolvedValueOnce([next, last, extra])
    .mockResolvedValueOnce([{ ...next, priority: 1 }, last, extra])
    .mockResolvedValueOnce([{ ...next, priority: 1 }, { ...last, priority: 1 }, extra])
  vi.mocked(api.queueTorrentFiles).mockResolvedValue(task)

  render(DownloadsPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })

  await fireEvent.click(await screen.findByRole('button', { name: 'Показать файлы' }))
  const file = await screen.findByText(next.name)
  const row = within(file.closest('li')!)
  expect(row.getByText(/18%/)).toBeTruthy()
  await fireEvent.click(row.getByRole('button', { name: 'Добавить в загрузку' }))
  expect(api.queueTorrentFiles).toHaveBeenCalledWith(task.id, 2)
  expect(await row.findByText(/18% · В загрузке/)).toBeTruthy()

  await fireEvent.click(screen.getByRole('button', { name: 'Скачать оставшиеся видео' }))
  expect(api.queueTorrentFiles).toHaveBeenLastCalledWith(task.id, undefined)
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Добавить в загрузку' })).toBeNull())
  expect(screen.queryByRole('button', { name: 'Скачать оставшиеся видео' })).toBeNull()
})
