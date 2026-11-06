import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import { afterEach, expect, test } from 'vitest'

import EpisodeList from './EpisodeList.vue'

afterEach(cleanup)

const episode = {
  id: 601,
  season_number: 2,
  number: 1,
  name: 'Возвращение',
  overview: 'Первая серия сезона.',
  air_date: '2025-01-10',
  runtime_minutes: 52,
  still_url: 'https://image.tmdb.org/episode.jpg',
  rating: 8.4,
}

test('renders episode metadata and emits the selected episode', async () => {
  const { emitted } = render(EpisodeList, { props: { episodes: [episode] } })

  expect(screen.getByText('Серия 1')).toBeTruthy()
  expect(screen.getByText('Возвращение')).toBeTruthy()
  expect(screen.getByText('52 мин.')).toBeTruthy()
  expect(screen.getByAltText('Кадр: Возвращение')).toBeTruthy()

  await fireEvent.click(screen.getByRole('button', { name: /Возвращение/ }))

  expect(emitted().select).toEqual([[episode]])
})

test('shows a controlled retry state when episode metadata is unavailable', async () => {
  const { emitted } = render(EpisodeList, {
    props: { episodes: [], error: 'Сервис временно недоступен.' },
  })

  expect(screen.getByText('Эпизоды недоступны')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  expect(emitted().retry).toHaveLength(1)
})

test('moves focus both up and down between episode actions', async () => {
  Element.prototype.scrollIntoView = () => undefined
  const episodes = [1, 2, 3].map((number) => ({
    ...episode,
    id: 600 + number,
    number,
    name: `Серия ${number}`,
  }))
  render(EpisodeList, { props: { episodes } })
  const playButtons = screen.getAllByRole('button', { name: /Серия \d/ })

  playButtons[1].focus()
  await fireEvent.keyDown(playButtons[1], { key: 'ArrowUp' })
  expect(document.activeElement).toBe(playButtons[0])

  await fireEvent.keyDown(playButtons[0], { key: 'ArrowDown' })
  expect(document.activeElement).toBe(playButtons[1])
})

test('renders persisted progress and emits a watched-state toggle', async () => {
  const history = [{
    id: 'history-1',
    media_id: 42,
    media_kind: 'series' as const,
    profile_key: 'default',
    season_number: 2,
    episode_number: 1,
    catalog_episode_id: 601,
    episode: null,
    title: 'Сериал',
    poster_url: null,
    position_seconds: 0,
    duration_seconds: 3120,
    completed: true,
    updated_at: '2026-11-06T00:00:00Z',
  }]
  const view = render(EpisodeList, { props: { episodes: [episode], history } })

  expect(screen.getByText('Просмотрено')).toBeTruthy()
  await fireEvent.click(screen.getByRole('button', { name: 'Отметить серию 1 непросмотренной' }))
  expect(view.emitted()['toggle-watched']).toEqual([[episode]])
})
