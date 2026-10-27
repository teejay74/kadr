import { fireEvent, render, screen } from '@testing-library/vue'
import { expect, test } from 'vitest'

import EpisodeList from './EpisodeList.vue'

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
