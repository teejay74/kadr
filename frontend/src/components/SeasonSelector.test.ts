import { fireEvent, render, screen } from '@testing-library/vue'
import { expect, test } from 'vitest'

import SeasonSelector from './SeasonSelector.vue'

const seasons = [
  { id: 1, number: 1, name: 'Сезон 1', episode_count: 8, air_date: null, poster_url: null },
  { id: 2, number: 2, name: 'Сезон 2', episode_count: 10, air_date: null, poster_url: null },
]

test('renders seasons and emits a numeric season number', async () => {
  const { emitted } = render(SeasonSelector, {
    props: { seasons, modelValue: 1 },
  })

  const select = screen.getByLabelText('Сезон')
  await fireEvent.update(select, '2')

  expect(emitted()['update:modelValue']).toEqual([[2]])
})
