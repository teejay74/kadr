import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import KadrPlayer from './KadrPlayer.vue'

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => undefined)
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({
        state: 'idle',
        progress: 0,
        strategy: null,
        video_codec: null,
        audio_codec: null,
        message: null,
        stream_url: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (url.endsWith('/stream/readiness')) {
      return new Response(JSON.stringify({
        ready: true,
        buffer_progress: 1,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  }))
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

test('opens the stream only after an explicit user action and closes it', async () => {
  render(KadrPlayer, { props: { taskId: 'task/id', title: 'Video.mp4' } })

  expect(document.querySelector('video')).toBeNull()
  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())

  const player = document.querySelector('video')
  expect(player?.getAttribute('src')).toBe('/api/v1/torrents/task%2Fid/stream')
  expect(player?.controls).toBe(true)

  await fireEvent.click(screen.getByRole('button', { name: 'Закрыть плеер' }))
  expect(document.querySelector('video')).toBeNull()
})

test('offers the saved playback position after metadata is available', async () => {
  localStorage.setItem('kadr:playback:task-id', '125')
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mp4' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const player = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(player, 'duration', { configurable: true, value: 600 })
  await fireEvent.loadedMetadata(player)

  expect(screen.getByText('Продолжить с 2:05?')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  expect(player.currentTime).toBe(125)
})

test('shows a controlled message when the browser rejects the stream', async () => {
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mp4' } })
  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  await fireEvent.error(document.querySelector('video') as HTMLVideoElement)

  expect(screen.getByRole('alert').textContent).toContain('Не удалось открыть видеопоток')
})

test('explains a codec error and can retry with a fresh stream request', async () => {
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })
  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const player = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(player, 'error', {
    configurable: true,
    value: { code: 3, message: 'decode failed' },
  })

  await fireEvent.error(player)
  expect(screen.getByRole('alert').textContent).toContain('совместимую версию')

  await fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  expect(player.getAttribute('src')).toContain('?attempt=1')
  expect(player.play).toHaveBeenCalled()
})

test('clears a completed position and does not restore it while closing', async () => {
  localStorage.setItem('kadr:playback:task-id', '125')
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mp4' } })
  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const player = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(player, 'currentTime', { configurable: true, value: 600 })

  await fireEvent.ended(player)
  await fireEvent.click(screen.getByRole('button', { name: 'Закрыть плеер' }))

  expect(localStorage.getItem('kadr:playback:task-id')).toBeNull()
})

test('waits for the startup buffer before attaching the video stream', async () => {
  vi.mocked(fetch).mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({ state: 'idle', progress: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(JSON.stringify({
      ready: false,
      buffer_progress: 0.25,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mp4' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))

  await screen.findByText('Подготавливаем буфер… 25%')
  expect(document.querySelector('video')).toBeNull()
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/torrents/task-id/stream/readiness',
    expect.anything(),
  )
})

test('explicitly prepares and opens a compatible FFmpeg version', async () => {
  vi.mocked(fetch).mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({
        state: 'ready',
        progress: 1,
        strategy: 'audio_transcode',
        video_codec: 'h264',
        audio_codec: 'ac3',
        message: null,
        stream_url: '/api/v1/torrents/task-id/compatible/stream',
      }), { status: 202, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByText('Если нет изображения или звука'))
  await fireEvent.click(screen.getByRole('button', { name: 'Подготовить совместимую версию' }))

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/v1/torrents/task-id/compatible/stream?attempt=1',
  )
})

test('automatically reuses a compatible version on the next playback attempt', async () => {
  vi.mocked(fetch).mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({
        state: 'ready',
        progress: 1,
        strategy: 'audio_transcode',
        video_codec: 'h264',
        audio_codec: 'ac3',
        message: null,
        stream_url: '/api/v1/torrents/task-id/compatible/stream',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/v1/torrents/task-id/compatible/stream?attempt=1',
  )
  expect(fetch).not.toHaveBeenCalledWith(
    '/api/v1/torrents/task-id/stream/readiness',
    expect.anything(),
  )
})
