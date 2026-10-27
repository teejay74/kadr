import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { afterEach, expect, test } from 'vitest'

import type { EpisodeMatchReport } from '../types/media'
import EpisodeMatchDialog from './EpisodeMatchDialog.vue'

afterEach(cleanup)

const report: EpisodeMatchReport = {
  task_id: 'task-id',
  metadata_available: true,
  requires_confirmation: true,
  files: [
    {
      file_id: 7,
      file_path: 'Season 1/Combined Feature.mkv',
      confidence: 'ambiguous',
      episodes: [
        {
          season_number: 1,
          episode_number: 1,
          catalog_episode_id: 101,
          name: 'Начало',
          runtime_minutes: 45,
        },
        {
          season_number: 1,
          episode_number: 2,
          catalog_episode_id: 102,
          name: 'Продолжение',
          runtime_minutes: 46,
        },
      ],
      alternatives: [],
      reasons: ['Один файл может содержать несколько эпизодов.'],
      confirmed: false,
      confirmation: null,
      unsafe: false,
      duration_seconds: null,
    },
  ],
}

test('confirms multiple episodes for one file and explains combined playback limit', async () => {
  const result = render(EpisodeMatchDialog, { props: { report } })

  expect(screen.getByText(/не сможет перейти к началу второй без временных границ/i)).toBeTruthy()
  expect((screen.getByRole('checkbox', { name: /S1E1/ }) as HTMLInputElement).checked).toBe(true)
  expect((screen.getByRole('checkbox', { name: /S1E2/ }) as HTMLInputElement).checked).toBe(true)

  await fireEvent.click(screen.getByRole('button', { name: 'Сохранить соответствия' }))

  expect(result.emitted().confirm).toEqual([[
    [{
      file_id: 7,
      episodes: report.files[0].episodes,
    }],
  ]])
})

test('does not offer confirmation for an unsafe path', () => {
  render(EpisodeMatchDialog, {
    props: {
      report: {
        ...report,
        files: [{
          ...report.files[0],
          file_path: '../Season 1/Show.S01E01.mkv',
          episodes: [],
          unsafe: true,
        }],
      },
    },
  })

  expect(screen.getByText(/небезопасен/i)).toBeTruthy()
  expect((screen.getByRole('button', {
    name: 'Сохранить соответствия',
  }) as HTMLButtonElement).disabled).toBe(true)
})
