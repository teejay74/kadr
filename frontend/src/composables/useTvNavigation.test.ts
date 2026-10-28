import { expect, test } from 'vitest'

import { findNextFocus } from './useTvNavigation'

function item(left: number, top: number, width = 100, height = 60): HTMLButtonElement {
  const element = document.createElement('button')
  element.getBoundingClientRect = () => ({
    bottom: top + height,
    height,
    left,
    right: left + width,
    top,
    width,
    x: left,
    y: top,
    toJSON: () => ({}),
  })
  return element
}

test('moves to the nearest item in the requested row or column', () => {
  const current = item(100, 100)
  const right = item(240, 100)
  const diagonal = item(210, 230)
  const below = item(100, 260)
  const candidates = [current, right, diagonal, below]

  expect(findNextFocus(current, candidates, 'right')).toBe(right)
  expect(findNextFocus(current, candidates, 'down')).toBe(below)
})

test('does not wrap focus to an item behind the requested direction', () => {
  const current = item(100, 100)
  const left = item(0, 100)

  expect(findNextFocus(current, [current, left], 'right')).toBeNull()
})
