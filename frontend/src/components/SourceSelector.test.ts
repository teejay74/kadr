import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { afterEach, expect, test } from 'vitest'

import type { SourceRelease } from '../types/media'
import SourceSelector from './SourceSelector.vue'

afterEach(cleanup)

const sources: SourceRelease[] = [
  {
    id: 'a'.repeat(24),
    title: 'Show.S01.2160p.WEB-DL.HEVC',
    indexer: 'Indexer A',
    size_bytes: 20_000_000_000,
    seeders: 2,
    peers: 1,
    published_at: null,
    season_number: 1,
    season_numbers: [1],
    protocol: 'torrent',
    resolution: '2160p',
    source: 'WEB-DL',
    codec: 'HEVC',
    hdr: false,
    hdr_format: null,
    audio: null,
    language: 'RU',
    release_type: 'web',
  },
  {
    id: 'b'.repeat(24),
    title: 'Show.S01.1080p.WEB-DL.H264',
    indexer: 'Indexer B',
    size_bytes: 8_000_000_000,
    seeders: 18,
    peers: 2,
    published_at: null,
    season_number: 1,
    season_numbers: [1],
    protocol: 'torrent',
    resolution: '1080p',
    source: 'WEB-DL',
    codec: 'H264',
    hdr: false,
    hdr_format: null,
    audio: 'Дубляж',
    language: null,
    release_type: 'web',
  },
]

test('shows normalized source information and hides raw title in technical details', async () => {
  render(SourceSelector, { props: { title: 'Сериал', items: sources } })

  expect(screen.getByRole('dialog', { name: 'Выберите источник' })).toBeTruthy()
  expect(screen.getByText('1080p')).toBeTruthy()
  expect(screen.getByText('Дубляж')).toBeTruthy()
  expect(screen.getByText('18')).toBeTruthy()
  expect(screen.getByText('Рекомендуемый для проверки')).toBeTruthy()
  expect(screen.getByText(/не гарантирует воспроизведение/i)).toBeTruthy()

  const details = screen.getAllByText('Технические подробности')[1]
  expect(details.parentElement?.hasAttribute('open')).toBe(false)
})

test('emits the selected normalized source', async () => {
  const result = render(SourceSelector, { props: { title: 'Сериал', items: sources } })

  await fireEvent.click(screen.getAllByRole('button', { name: 'Выбрать' })[1])

  expect(result.emitted().select).toEqual([[sources[1]]])
})
