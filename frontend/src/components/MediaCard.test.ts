import { render, screen } from '@testing-library/vue'
import { expect, test } from 'vitest'

import MediaCard from './MediaCard.vue'

test('renders real media metadata and accessible poster text', () => {
  render(MediaCard, {
    props: {
      media: {
        id: 11,
        kind: 'movie',
        title: 'Звёздные войны',
        original_title: 'Star Wars',
        overview: '',
        release_date: '1977-05-25',
        year: 1977,
        poster_url: 'https://image.tmdb.org/poster.jpg',
        backdrop_url: null,
        rating: 8.2,
        popularity: 10,
        genre_ids: [12],
      },
    },
    global: {
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })

  expect(screen.getByText('Звёздные войны')).toBeTruthy()
  expect(screen.getByAltText('Постер: Звёздные войны')).toBeTruthy()
  expect(screen.getByText('★ 8.2')).toBeTruthy()
})
