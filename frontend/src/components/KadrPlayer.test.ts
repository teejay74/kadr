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
        file_progress: 1,
        download_state: null,
        download_speed_bytes: 0,
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
  expect(player?.play).toHaveBeenCalled()

  await fireEvent.click(screen.getByRole('button', { name: 'Закрыть плеер' }))
  expect(document.querySelector('video')).toBeNull()
})

test('automatically activates after a unified playback resolution', async () => {
  render(KadrPlayer, {
    props: {
      taskId: 'resolved-task',
      title: 'Resolved video',
      autoActivate: true,
      initialResumeSeconds: 45,
    },
  })

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/v1/torrents/resolved-task/stream',
  )
  expect(fetch).not.toHaveBeenCalledWith(
    '/api/v1/history/0?media_kind=movie',
    expect.anything(),
  )
})

test('opens a resolved library stream without probing torrent compatibility', async () => {
  render(KadrPlayer, {
    props: {
      taskId: 'saved-task',
      title: 'Saved video',
      directStreamUrl: '/api/v1/library/saved-item/stream',
      autoActivate: true,
    },
  })

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/v1/library/saved-item/stream',
  )
  expect(fetch).not.toHaveBeenCalled()
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
      file_progress: 0.4,
      download_state: 'downloading',
      download_speed_bytes: 1_048_576,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mp4' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))

  await screen.findByText('Подготавливаем начальный буфер… 25%')
  expect(screen.getAllByText(/Скачано 40% · эпизод загружается · 1.0 МБ\/с/).length).toBeGreaterThan(0)
  expect(screen.getByText('KADR автоматически проверяет готовность потока каждые 5 секунд.')).toBeTruthy()
  expect(document.querySelector('video')).toBeNull()
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/torrents/task-id/stream/readiness',
    expect.anything(),
  )
})

test('explains when the browser blocks automatic playback', async () => {
  vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new Error('blocked'))
  render(KadrPlayer, {
    props: {
      taskId: 'task-id',
      title: 'Video.mp4',
      downloadProgress: 0.4,
      downloadState: 'downloading',
      downloadSpeedBytes: 1_048_576,
    },
  })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))

  expect((await screen.findByRole('alert')).textContent).toContain(
    'браузер заблокировал автоматический запуск',
  )
  expect(screen.getByText('Скачано 100% · файл загружен полностью')).toBeTruthy()
  expect(document.querySelector('video')).not.toBeNull()
})

test('explicitly prepares and opens a compatible FFmpeg version', async () => {
  vi.mocked(fetch).mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({
        mode: 'compatible',
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
  await fireEvent.click(screen.getByRole('button', { name: 'Полная совместимая версия' }))

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/v1/torrents/task-id/compatible/stream?attempt=1',
  )
})

test('shows and cancels a queued compatible preparation', async () => {
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/compatible') && init?.method === 'POST') {
      return new Response(JSON.stringify({
        mode: 'compatible',
        state: 'queued',
        progress: 0,
        queue_position: 2,
      }), { status: 202, headers: { 'Content-Type': 'application/json' } })
    }
    if (url.endsWith('/compatible') && init?.method === 'DELETE') {
      return new Response(JSON.stringify({
        mode: 'compatible',
        state: 'idle',
        progress: 0,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByText('Если нет изображения или звука'))
  await fireEvent.click(screen.getByRole('button', { name: 'Полная совместимая версия' }))

  expect(await screen.findByText(/В очереди на подготовку/)).toBeTruthy()
  expect(screen.getByText(/позиция 2/)).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Убрать из очереди' }))

  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/api/v1/torrents/task-id/compatible',
    expect.objectContaining({ method: 'DELETE' }),
  ))
})

test('quickly fixes audio without requesting a full video transcode', async () => {
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/compatible?mode=audio_only') && init?.method === 'POST') {
      return new Response(JSON.stringify({
        mode: 'audio_only',
        state: 'ready',
        progress: 1,
        strategy: 'audio_transcode',
        video_codec: 'hevc',
        audio_codec: 'eac3',
        message: null,
        stream_url: '/api/v1/torrents/task-id/compatible/stream?mode=audio_only',
      }), { status: 202, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByText('Если нет изображения или звука'))
  await fireEvent.click(screen.getByRole('button', { name: 'Быстро исправить звук' }))

  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/v1/torrents/task-id/compatible/stream?mode=audio_only&attempt=1',
  )
})

test('lists tracks and switches a native audio track without losing position', async () => {
  const tracks = {
    source: 'torrent',
    source_id: 'task-id',
    file_id: 7,
    audio_tracks: [
      {
        id: 'audio-ru',
        preference_key: 'semantic-ru',
        stream_index: 1,
        kind: 'audio',
        language: 'ru',
        codec: 'ac3',
        title: 'Студия',
        is_default: true,
        is_forced: false,
        is_hearing_impaired: false,
        channels: 2,
        channel_layout: 'stereo',
        delivery: 'native_or_compatible',
      },
      {
        id: 'audio-en',
        preference_key: 'semantic-en',
        stream_index: 2,
        kind: 'audio',
        language: 'en',
        codec: 'aac',
        title: null,
        is_default: false,
        is_forced: false,
        is_hearing_impaired: false,
        channels: 2,
        channel_layout: 'stereo',
        delivery: 'native_or_compatible',
      },
    ],
    subtitle_tracks: [],
    selected_audio_track_id: 'audio-ru',
    selected_subtitle_track_id: null,
    subtitles_enabled: false,
  }
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({ state: 'idle', progress: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/stream/readiness')) {
      return new Response(JSON.stringify({
        ready: true,
        buffer_progress: 1,
        file_progress: 1,
        download_state: null,
        download_speed_bytes: 0,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (url.includes('/tracks?profile_key=default')) {
      return new Response(JSON.stringify(tracks), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/tracks/preferences') && init?.method === 'PUT') {
      return new Response(JSON.stringify({
        ...tracks,
        selected_audio_track_id: 'audio-en',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const player = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(player, 'currentTime', { configurable: true, writable: true, value: 42 })
  const russian = { id: 'native-ru', language: 'ru', label: 'Студия', enabled: true }
  const english = { id: 'native-en', language: 'en', label: '', enabled: false }
  Object.defineProperty(player, 'audioTracks', {
    configurable: true,
    value: { 0: russian, 1: english, length: 2 },
  })

  await fireEvent.click(screen.getByRole('button', { name: 'Аудио и субтитры' }))
  await screen.findByLabelText('Английский · 2 каналов · AAC')
  await fireEvent.click(screen.getByLabelText('Английский · 2 каналов · AAC'))

  await screen.findByText('Выбор применён без перезапуска потока.')
  expect(russian.enabled).toBe(false)
  expect(english.enabled).toBe(true)
  expect(player.currentTime).toBe(42)
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/torrents/task-id/tracks/preferences',
    expect.objectContaining({ method: 'PUT' }),
  )
})

test('explicitly prepares a selected audio stream and restores position', async () => {
  const tracks = {
    source: 'torrent',
    source_id: 'task-id',
    file_id: 7,
    audio_tracks: [
      {
        id: 'audio-ru',
        preference_key: 'semantic-ru',
        stream_index: 3,
        kind: 'audio',
        language: 'ru',
        codec: 'ac3',
        title: 'Studio',
        is_default: true,
        is_forced: false,
        is_hearing_impaired: false,
        channels: 2,
        channel_layout: 'stereo',
        delivery: 'native_or_compatible',
      },
      {
        id: 'audio-en',
        preference_key: 'semantic-en',
        stream_index: 4,
        kind: 'audio',
        language: 'en',
        codec: 'ac3',
        title: null,
        is_default: false,
        is_forced: false,
        is_hearing_impaired: false,
        channels: 2,
        channel_layout: 'stereo',
        delivery: 'native_or_compatible',
      },
    ],
    subtitle_tracks: [],
    selected_audio_track_id: 'audio-ru',
    selected_subtitle_track_id: null,
    subtitles_enabled: false,
  }
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({ state: 'idle', progress: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/stream/readiness')) {
      return new Response(JSON.stringify({
        ready: true,
        buffer_progress: 1,
        file_progress: 1,
        download_state: null,
        download_speed_bytes: 0,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (url.includes('/tracks?profile_key=default')) {
      return new Response(JSON.stringify(tracks), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/tracks/preferences')) {
      return new Response(JSON.stringify({
        ...tracks,
        selected_audio_track_id: 'audio-en',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (
      url.endsWith('/compatible?mode=audio_track&track_id=audio-en')
      && init?.method === 'POST'
    ) {
      return new Response(JSON.stringify({
        mode: 'audio_track',
        state: 'ready',
        progress: 1,
        strategy: 'audio_transcode',
        video_codec: 'h264',
        audio_codec: 'ac3',
        message: null,
        track_id: 'audio-en',
        stream_url: '/api/v1/torrents/task-id/compatible/stream?mode=audio_track&track_id=audio-en',
      }), { status: 202, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const original = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(original, 'currentTime', { configurable: true, writable: true, value: 73 })
  await fireEvent.click(screen.getByRole('button', { name: 'Аудио и субтитры' }))
  await screen.findByLabelText('Английский · 2 каналов · AC3')
  await fireEvent.click(screen.getByLabelText('Английский · 2 каналов · AC3'))
  await screen.findByText(/не умеет переключить дорожку/)

  await fireEvent.click(screen.getByRole('button', {
    name: 'Подготовить выбранную аудиодорожку',
  }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const compatiblePlayer = document.querySelector('video') as HTMLVideoElement
  expect(compatiblePlayer.getAttribute('src')).toContain(
    'mode=audio_track&track_id=audio-en&attempt=1',
  )
  Object.defineProperty(compatiblePlayer, 'duration', { configurable: true, value: 600 })
  await fireEvent.loadedMetadata(compatiblePlayer)
  expect(compatiblePlayer.currentTime).toBe(73)
})

test('explicitly prepares selected text subtitles and restores position', async () => {
  const tracks = {
    source: 'torrent',
    source_id: 'task-id',
    file_id: 7,
    audio_tracks: [],
    subtitle_tracks: [{
      id: 'subtitle-ru',
      preference_key: 'semantic-subtitle-ru',
      stream_index: 4,
      kind: 'subtitle',
      language: 'ru',
      codec: 'subrip',
      title: null,
      is_default: false,
      is_forced: false,
      is_hearing_impaired: false,
      channels: null,
      channel_layout: null,
      delivery: 'external_webvtt',
    }],
    selected_audio_track_id: null,
    selected_subtitle_track_id: null,
    subtitles_enabled: false,
  }
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({ state: 'idle', progress: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/stream/readiness')) {
      return new Response(JSON.stringify({
        ready: true,
        buffer_progress: 1,
        file_progress: 1,
        download_state: null,
        download_speed_bytes: 0,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (url.includes('/tracks?profile_key=default')) {
      return new Response(JSON.stringify(tracks), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/tracks/preferences')) {
      return new Response(JSON.stringify({
        ...tracks,
        selected_subtitle_track_id: 'subtitle-ru',
        subtitles_enabled: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (url.endsWith('/tracks/subtitle-ru/subtitle') && init?.method === 'POST') {
      return new Response(JSON.stringify({
        track_id: 'subtitle-ru',
        stream_url: '/api/v1/torrents/task-id/subtitles/artifact.vtt',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  render(KadrPlayer, { props: { taskId: 'task-id', title: 'Video.mkv' } })

  await fireEvent.click(screen.getByRole('button', { name: 'Начать просмотр' }))
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const player = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(player, 'currentTime', { configurable: true, writable: true, value: 91 })
  await fireEvent.click(screen.getByRole('button', { name: 'Аудио и субтитры' }))
  await fireEvent.click(await screen.findByLabelText('Русский · SUBRIP'))
  await fireEvent.click(await screen.findByRole('button', {
    name: 'Подготовить выбранные субтитры',
  }))

  await waitFor(() => expect(document.querySelector('track')?.getAttribute('src')).toBe(
    '/api/v1/torrents/task-id/subtitles/artifact.vtt',
  ))
  Object.defineProperty(player, 'duration', { configurable: true, value: 600 })
  await fireEvent.loadedMetadata(player)
  expect(player.currentTime).toBe(91)
})

test('automatically reuses a compatible version on the next playback attempt', async () => {
  vi.mocked(fetch).mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/compatible')) {
      return new Response(JSON.stringify({
        mode: 'compatible',
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

test('requests one next-episode prefetch near the end and emits completion', async () => {
  const view = render(KadrPlayer, {
    props: {
      taskId: 'task-id',
      title: 'Series',
      mediaId: 42,
      mediaKind: 'series',
      directStreamUrl: '/api/v1/library/saved/stream',
      autoActivate: true,
      episode: {
        id: 101,
        season_number: 1,
        number: 1,
        name: 'Episode 1',
        overview: '',
        air_date: null,
        runtime_minutes: 45,
        still_url: null,
        rating: 0,
      },
    },
  })
  await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  const player = document.querySelector('video') as HTMLVideoElement
  Object.defineProperty(player, 'duration', { configurable: true, value: 1800 })
  Object.defineProperty(player, 'currentTime', { configurable: true, value: 1720 })

  await fireEvent.timeUpdate(player)
  await fireEvent.timeUpdate(player)
  await fireEvent.ended(player)

  expect(view.emitted()['near-end']).toHaveLength(1)
  expect(view.emitted().ended).toHaveLength(1)
})
