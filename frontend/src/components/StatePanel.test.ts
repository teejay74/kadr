import { fireEvent, render, screen } from '@testing-library/vue'
import { expect, test } from 'vitest'

import StatePanel from './StatePanel.vue'

test('shows an explicit retry action and emits retry', async () => {
  const view = render(StatePanel, {
    props: {
      title: 'Каталог недоступен',
      message: 'Попробуйте снова',
      showRetry: true,
    },
  })

  await fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))

  expect(view.emitted().retry).toHaveLength(1)
})
