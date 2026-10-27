import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { afterEach, expect, test, vi } from 'vitest'

import NextEpisodeOverlay from './NextEpisodeOverlay.vue'

afterEach(cleanup)

test('shows backend-selected episode and persists an explicit play action', async () => {
  const view = render(NextEpisodeOverlay, {
    props: {
      loading: false,
      autoPlay: false,
      result: {
        status: 'ready',
        prefetched: true,
        combined_file: false,
        message: null,
        episode: {
          id: 202,
          season_number: 2,
          number: 2,
          name: 'Новый сезон',
          overview: '',
          air_date: null,
          runtime_minutes: 45,
          still_url: null,
          rating: 0,
        },
        playback: {
          status: 'ready',
          source: 'torrent',
          stream_url: '/stream',
          task_id: 'task',
          file_id: 7,
          library_item_id: null,
          resume_position_seconds: 0,
          buffer_progress: 1,
          download_progress: 1,
          download_state: 'uploading',
          download_speed_bytes: 0,
          message: null,
        },
      },
    },
  })

  expect(screen.getByText('Сезон 2 · Серия 2')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: '▶ Следующая серия' }))
  expect(view.emitted().play).toHaveLength(1)
})

test('autoplays only after the visible countdown when enabled', async () => {
  vi.useFakeTimers()
  const view = render(NextEpisodeOverlay, {
    props: {
      loading: false,
      autoPlay: true,
      result: {
        status: 'buffering',
        prefetched: true,
        combined_file: false,
        message: null,
        episode: {
          id: 102,
          season_number: 1,
          number: 2,
          name: 'Episode 2',
          overview: '',
          air_date: null,
          runtime_minutes: null,
          still_url: null,
          rating: 0,
        },
        playback: {
          status: 'buffering',
          source: 'torrent',
          stream_url: '/stream',
          task_id: 'task',
          file_id: 2,
          library_item_id: null,
          resume_position_seconds: 0,
          buffer_progress: 0.5,
          download_progress: 0.2,
          download_state: 'downloading',
          download_speed_bytes: 100,
          message: null,
        },
      },
    },
  })

  vi.advanceTimersByTime(5000)
  expect(view.emitted().play).toHaveLength(1)
  vi.useRealTimers()
})

test('offers source selection for a backend-owned next episode without a binding', async () => {
  const view = render(NextEpisodeOverlay, {
    props: {
      loading: false,
      autoPlay: false,
      result: {
        status: 'source_required',
        prefetched: false,
        combined_file: false,
        message: 'Choose source',
        episode: {
          id: 102,
          season_number: 1,
          number: 2,
          name: 'Episode 2',
          overview: '',
          air_date: null,
          runtime_minutes: null,
          still_url: null,
          rating: 0,
        },
        playback: null,
      },
    },
  })

  await fireEvent.click(screen.getByRole('button', { name: 'Выбрать источник' }))
  expect(view.emitted()['choose-source']).toHaveLength(1)
})
