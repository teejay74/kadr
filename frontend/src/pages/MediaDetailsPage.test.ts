import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import * as api from '../services/api'
import MediaDetailsPage from './MediaDetailsPage.vue'

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  addTorrent: vi.fn(),
  analyzeEpisodeMatches: vi.fn(),
  confirmEpisodeMatches: vi.fn(),
  getFavorites: vi.fn(),
  getMediaDetails: vi.fn(),
  getSources: vi.fn(),
  prefetchNextEpisode: vi.fn(),
  resolvePlayback: vi.fn(),
  resolveNextEpisode: vi.fn(),
  getSeriesSeason: vi.fn(),
  getTorrentFiles: vi.fn(),
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
const downloadsTestRoute = { path: '/downloads', component: { template: '<div />' } }

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
  vi.mocked(api.getSources).mockResolvedValue({
    media_id: 42,
    media_kind: 'series',
    query: 'Test Series S01',
    items: [],
    total: 0,
  })
  vi.mocked(api.getTorrentFiles).mockResolvedValue([])
  vi.mocked(api.prefetchNextEpisode).mockResolvedValue({
    status: 'source_required',
    episode: null,
    playback: null,
    prefetched: false,
    combined_file: false,
    message: null,
  })
  vi.mocked(api.resolvePlayback).mockResolvedValue({
    status: 'source_required',
    source: null,
    stream_url: null,
    task_id: null,
    file_id: null,
    library_item_id: null,
    resume_position_seconds: 0,
    buffer_progress: 0,
    download_progress: 0,
    download_state: null,
    download_speed_bytes: 0,
    message: 'Выберите источник для начала просмотра.',
  })
})

afterEach(cleanup)

test('asks the backend to resolve an episode before opening the source selector', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/series/:id', component: MediaDetailsPage, meta: { kind: 'series' } }, downloadsTestRoute],
  })
  await router.push('/series/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: { SourcesPanel: { template: '<section id="media-sources">Legacy sources</section>' } },
    },
  })

  await fireEvent.click(await screen.findByRole('button', { name: /Эпизод сезона 1/ }))

  await waitFor(() => expect(api.resolvePlayback).toHaveBeenCalledWith(
    42,
    'series',
    expect.objectContaining({ season_number: 1, number: 1 }),
  ))
  expect(await screen.findByText(/Выберите источник для начала просмотра/)).toBeTruthy()
  expect(screen.getByRole('dialog', { name: 'Выберите источник' })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Открыть загрузки' })).toBeTruthy()
})

test('opens the shared player when the backend resolves a saved episode', async () => {
  vi.mocked(api.resolvePlayback).mockResolvedValueOnce({
    status: 'ready',
    source: 'library',
    stream_url: '/api/v1/library/saved/stream',
    task_id: 'task-id',
    file_id: 1,
    library_item_id: 'saved',
    resume_position_seconds: 90,
    buffer_progress: 1,
    download_progress: 1,
    download_state: 'saved',
    download_speed_bytes: 0,
    message: null,
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/series/:id', component: MediaDetailsPage, meta: { kind: 'series' } }, downloadsTestRoute],
  })
  await router.push('/series/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: {
        SourcesPanel: { template: '<section id="media-sources">Legacy sources</section>' },
        KadrPlayer: { template: '<div>Unified player</div>' },
      },
    },
  })

  await fireEvent.click(await screen.findByRole('button', { name: /Эпизод сезона 1/ }))

  expect(await screen.findByText('Unified player')).toBeTruthy()
  expect(screen.queryByText(/Для ручного выбора/)).toBeNull()
})

test('uses the same backend resolver for the movie primary action', async () => {
  vi.mocked(api.getMediaDetails).mockResolvedValueOnce({
    ...details,
    kind: 'movie',
    title: 'Тестовый фильм',
    seasons: [],
    season_count: null,
    episode_count: null,
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/movies/:id', component: MediaDetailsPage, meta: { kind: 'movie' } }, downloadsTestRoute],
  })
  await router.push('/movies/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: { SourcesPanel: { template: '<section id="media-sources">Legacy sources</section>' } },
    },
  })

  await fireEvent.click(await screen.findByRole('button', { name: 'Смотреть' }))

  await waitFor(() => expect(api.resolvePlayback).toHaveBeenCalledWith(42, 'movie', null))
  expect(await screen.findByText(/Выберите источник для начала просмотра/)).toBeTruthy()
  expect(screen.getByRole('dialog', { name: 'Выберите источник' })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Открыть загрузки' })).toBeTruthy()
})

test('selects a movie source in the modal and retries unified playback', async () => {
  vi.mocked(api.getMediaDetails).mockResolvedValueOnce({
    ...details,
    kind: 'movie',
    title: 'Тестовый фильм',
    seasons: [],
    season_count: null,
    episode_count: null,
  })
  vi.mocked(api.getSources).mockResolvedValueOnce({
    media_id: 42,
    media_kind: 'movie',
    query: 'Тестовый фильм 2024',
    total: 1,
    items: [{
      id: 'a'.repeat(24),
      title: 'Movie.1080p.WEB-DL.H264',
      indexer: 'Indexer',
      size_bytes: 8_000_000_000,
      seeders: 10,
      peers: 1,
      published_at: null,
      season_number: null,
      season_numbers: [],
      protocol: 'torrent',
      resolution: '1080p',
      source: 'WEB-DL',
      codec: 'H264',
      hdr: false,
      hdr_format: null,
      audio: 'Дубляж',
      language: 'RU',
      release_type: 'web',
    }],
  })
  vi.mocked(api.addTorrent).mockResolvedValue({
    id: 'task-id',
    media_id: 42,
    media_kind: 'movie',
    name: 'Movie',
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
  vi.mocked(api.getTorrentFiles).mockResolvedValueOnce([{
    id: 1,
    name: 'Movie.mkv',
    size_bytes: 100,
    progress: 0,
    priority: 0,
    is_video: true,
    duration_seconds: null,
  }])
  vi.mocked(api.resolvePlayback)
    .mockResolvedValueOnce({
      status: 'source_required',
      source: null,
      stream_url: null,
      task_id: null,
      file_id: null,
      library_item_id: null,
      resume_position_seconds: 0,
      buffer_progress: 0,
      download_progress: 0,
      download_state: null,
      download_speed_bytes: 0,
      message: 'Выберите источник для начала просмотра.',
    })
    .mockResolvedValueOnce({
      status: 'buffering',
      source: 'torrent',
      stream_url: '/api/v1/torrents/task-id/stream',
      task_id: 'task-id',
      file_id: 1,
      library_item_id: null,
      resume_position_seconds: 0,
      buffer_progress: 0.4,
      download_progress: 0,
      download_state: 'downloading',
      download_speed_bytes: 100,
      message: null,
    })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/movies/:id', component: MediaDetailsPage, meta: { kind: 'movie' } }, downloadsTestRoute],
  })
  await router.push('/movies/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: {
        SourcesPanel: { template: '<section id="media-sources">Legacy sources</section>' },
        KadrPlayer: { template: '<div>Unified player</div>' },
      },
    },
  })

  await fireEvent.click(await screen.findByRole('button', { name: 'Смотреть' }))
  await fireEvent.click(await screen.findByRole('button', { name: 'Выбрать' }))

  expect(await screen.findByText('Unified player')).toBeTruthy()
  expect(api.addTorrent).toHaveBeenCalledWith(42, 'movie', 'a'.repeat(24), null)
  expect(api.resolvePlayback).toHaveBeenCalledTimes(2)
})

test('opens episode confirmation when the selected series source is ambiguous', async () => {
  vi.mocked(api.getSources).mockResolvedValueOnce({
    media_id: 42,
    media_kind: 'series',
    query: 'Test Series S01',
    total: 1,
    items: [{
      id: 'b'.repeat(24),
      title: 'Test.Series.S01.1080p.WEB-DL',
      indexer: 'Indexer',
      size_bytes: 8_000_000_000,
      seeders: 12,
      peers: 1,
      published_at: null,
      season_number: 1,
      season_numbers: [1],
      protocol: 'torrent',
      resolution: '1080p',
      source: 'WEB-DL',
      codec: 'H264',
      hdr: false,
      hdr_format: null,
      audio: null,
      language: 'RU',
      release_type: 'web',
    }],
  })
  vi.mocked(api.addTorrent).mockResolvedValue({
    id: 'series-task',
    media_id: 42,
    media_kind: 'series',
    name: 'Test Series',
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
  vi.mocked(api.getTorrentFiles).mockResolvedValueOnce([{
    id: 2,
    name: 'Season 1/Combined Feature.mkv',
    size_bytes: 100,
    progress: 0,
    priority: 0,
    is_video: true,
    duration_seconds: null,
  }])
  vi.mocked(api.analyzeEpisodeMatches).mockResolvedValueOnce({
    task_id: 'series-task',
    metadata_available: true,
    requires_confirmation: true,
    files: [{
      file_id: 2,
      file_path: 'Season 1/Combined Feature.mkv',
      confidence: 'ambiguous',
      episodes: [{
        season_number: 1,
        episode_number: 1,
        catalog_episode_id: 601,
        name: 'Эпизод сезона 1',
        runtime_minutes: 50,
      }],
      alternatives: [],
      reasons: ['Требуется подтверждение.'],
      confirmed: false,
      confirmation: null,
      unsafe: false,
      duration_seconds: null,
    }],
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/series/:id', component: MediaDetailsPage, meta: { kind: 'series' } }, downloadsTestRoute],
  })
  await router.push('/series/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: { SourcesPanel: { template: '<section id="media-sources">Legacy sources</section>' } },
    },
  })

  await fireEvent.click(await screen.findByRole('button', { name: /Эпизод сезона 1/ }))
  await fireEvent.click(await screen.findByRole('button', { name: 'Выбрать' }))

  expect(await screen.findByRole('dialog', { name: 'Проверьте соответствия серий' })).toBeTruthy()
  expect(api.analyzeEpisodeMatches).toHaveBeenCalledWith('series-task')
})

test('restores the last season and reloads episodes after season selection', async () => {
  localStorage.setItem('kadr:season:42', '2')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/series/:id', component: MediaDetailsPage, meta: { kind: 'series' } }, downloadsTestRoute],
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

test('uses the backend next episode across seasons and opens it in the shared player', async () => {
  const currentPlayback = {
    status: 'ready' as const,
    source: 'torrent' as const,
    stream_url: '/api/v1/torrents/task-id/stream',
    task_id: 'task-id',
    file_id: 1,
    library_item_id: null,
    resume_position_seconds: 0,
    buffer_progress: 1,
    download_progress: 0.8,
    download_state: 'downloading',
    download_speed_bytes: 100,
    message: null,
  }
  vi.mocked(api.resolvePlayback).mockResolvedValueOnce(currentPlayback)
  vi.mocked(api.resolveNextEpisode).mockResolvedValueOnce({
    status: 'ready',
    prefetched: true,
    combined_file: false,
    message: null,
    episode: season(2).episodes[0],
    playback: { ...currentPlayback, file_id: 7 },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/series/:id', component: MediaDetailsPage, meta: { kind: 'series' } }, downloadsTestRoute],
  })
  await router.push('/series/42')
  await router.isReady()

  render(MediaDetailsPage, {
    global: {
      plugins: [router],
      stubs: {
        SourcesPanel: { template: '<section>Legacy sources</section>' },
        KadrPlayer: {
          props: ['selectionLabel'],
          emits: ['near-end', 'ended'],
          template: '<div><span>{{ selectionLabel }}</span><button @click="$emit(\'ended\')">Finish episode</button></div>',
        },
      },
    },
  })

  await fireEvent.click(await screen.findByRole('button', { name: /Эпизод сезона 1/ }))
  await fireEvent.click(await screen.findByRole('button', { name: 'Finish episode' }))
  await fireEvent.click(await screen.findByRole('button', { name: '▶ Следующая серия' }))

  expect(await screen.findByText('Сезон 2 · Серия 1')).toBeTruthy()
  expect(api.resolveNextEpisode).toHaveBeenCalledWith(42, expect.objectContaining({ number: 1 }), 'task-id', 1)
  expect(api.getSeriesSeason).toHaveBeenCalledWith(42, 2)
})
