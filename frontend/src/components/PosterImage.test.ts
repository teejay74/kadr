import { fireEvent, render, screen } from '@testing-library/vue'
import { expect, test } from 'vitest'
import PosterImage from './PosterImage.vue'
import { imageUrl } from '../services/images'

test('routes legacy TMDB links to KADR and rejects invalid TMDB paths', () => {
  expect(imageUrl('https://image.tmdb.org/t/p/w500/poster.jpg')).toBe('/api/v1/posters/w500/poster.jpg')
  expect(imageUrl('/api/v1/posters/w342/poster.jpg')).toBe('/api/v1/posters/w342/poster.jpg')
  expect(imageUrl('https://image.tmdb.org/t/p/w501/poster.jpg')).toBeNull()
  expect(imageUrl('https://image.tmdb.org/t/p/w500/a.jpg?url=evil')).toBeNull()
})

test('shows placeholder on error and retries when source changes', async () => {
  const view = render(PosterImage, { props: { src: 'https://image.tmdb.org/t/p/w500/a.jpg', alt: 'Постер' } })
  expect(screen.getByAltText('Постер').getAttribute('src')).toBe('/api/v1/posters/w500/a.jpg')
  await fireEvent.error(screen.getByAltText('Постер'))
  expect(screen.queryByAltText('Постер')).toBeNull()
  expect(screen.getByText('K')).toBeTruthy()
  await view.rerender({ src: '/api/v1/posters/w500/b.jpg' })
  expect(screen.getByAltText('Постер').getAttribute('src')).toBe('/api/v1/posters/w500/b.jpg')
})
