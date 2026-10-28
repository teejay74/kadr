import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import type { Ref } from 'vue'
import type { Router } from 'vue-router'

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'summary',
  '[role="button"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

type Direction = 'up' | 'down' | 'left' | 'right'

function isVisible(element: HTMLElement): boolean {
  const style = window.getComputedStyle(element)
  const rect = element.getBoundingClientRect()
  return style.display !== 'none'
    && style.visibility !== 'hidden'
    && !element.hasAttribute('hidden')
    && rect.width > 0
    && rect.height > 0
}

function isTextControl(element: HTMLElement): boolean {
  return element instanceof HTMLInputElement
    || element instanceof HTMLTextAreaElement
    || element instanceof HTMLSelectElement
    || element.isContentEditable
}

export function getFocusableElements(root: ParentNode = document): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(focusableSelector)).filter(isVisible)
}

export function findNextFocus(
  current: HTMLElement,
  candidates: HTMLElement[],
  direction: Direction,
): HTMLElement | null {
  const currentRect = current.getBoundingClientRect()
  const currentX = currentRect.left + currentRect.width / 2
  const currentY = currentRect.top + currentRect.height / 2
  let best: HTMLElement | null = null
  let bestScore = Number.POSITIVE_INFINITY

  for (const candidate of candidates) {
    if (candidate === current) continue
    const rect = candidate.getBoundingClientRect()
    const x = rect.left + rect.width / 2
    const y = rect.top + rect.height / 2
    const deltaX = x - currentX
    const deltaY = y - currentY
    const primary = direction === 'left' || direction === 'right' ? Math.abs(deltaX) : Math.abs(deltaY)
    const secondary = direction === 'left' || direction === 'right' ? Math.abs(deltaY) : Math.abs(deltaX)
    const isAhead = direction === 'left'
      ? deltaX < -1
      : direction === 'right'
        ? deltaX > 1
        : direction === 'up'
          ? deltaY < -1
          : deltaY > 1
    if (!isAhead) continue

    // Prefer the nearest item in the requested direction while strongly
    // favouring elements that remain in the same visual row or column.
    const score = primary + secondary * 3 + (secondary > primary * 1.5 ? secondary * 2 : 0)
    if (score < bestScore) {
      best = candidate
      bestScore = score
    }
  }
  return best
}

function detectTvMode(): boolean {
  const override = new URLSearchParams(window.location.search).get('tv')
  if (override === '1') return true
  if (override === '0') return false
  const tvUserAgent = /Android.*(?:TV|AFT)|GoogleTV|SMART-TV|BRAVIA/i.test(navigator.userAgent)
  const coarseLargeScreen = typeof window.matchMedia === 'function'
    && window.matchMedia('(pointer: coarse) and (min-width: 960px)').matches
  return tvUserAgent || coarseLargeScreen
}

export function useTvNavigation(router: Router): { tvMode: Ref<boolean> } {
  const tvMode = ref(false)

  function focusElement(element: HTMLElement): void {
    element.focus({ preventScroll: true })
    element.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
  }

  function focusPageStart(): void {
    if (!tvMode.value) return
    const preferred = document.querySelector<HTMLElement>('[data-tv-autofocus]')
    const target = preferred && isVisible(preferred)
      ? preferred
      : getFocusableElements(document.querySelector('main') ?? document)[0]
    if (target) focusElement(target)
  }

  function runBackAction(): boolean {
    const actions = getFocusableElements().filter((element) => element.hasAttribute('data-tv-back-action'))
    const action = actions.at(-1)
    if (!action) return false
    action.click()
    return true
  }

  function onKeydown(event: KeyboardEvent): void {
    if (!tvMode.value) return
    const current = document.activeElement instanceof HTMLElement ? document.activeElement : null

    const isBack = event.key === 'Escape'
      || event.key === 'BrowserBack'
      || event.key === 'GoBack'
      || event.keyCode === 4
      || (event.key === 'Backspace' && !(current && isTextControl(current)))
    if (isBack) {
      event.preventDefault()
      if (current && isTextControl(current)) {
        current.blur()
        return
      }
      if (!runBackAction()) {
        const hasBackEntry = Boolean(window.history.state?.back)
        if (hasBackEntry) router.back()
        else if (router.currentRoute.value.path !== '/') void router.push('/')
      }
      return
    }

    if (event.key === 'Select' && current && getFocusableElements().includes(current)) {
      event.preventDefault()
      current.click()
      return
    }

    const directions: Partial<Record<string, Direction>> = {
      ArrowUp: 'up',
      ArrowDown: 'down',
      ArrowLeft: 'left',
      ArrowRight: 'right',
    }
    const direction = directions[event.key]
    if (!direction || (current && isTextControl(current))) return
    const candidates = getFocusableElements()
    if (!current || !candidates.includes(current)) {
      const first = candidates[0]
      if (first) {
        event.preventDefault()
        focusElement(first)
      }
      return
    }
    const next = findNextFocus(current, candidates, direction)
    if (next) {
      event.preventDefault()
      focusElement(next)
    }
  }

  const removeRouteHook = router.afterEach(() => {
    void nextTick(focusPageStart)
  })

  onMounted(() => {
    tvMode.value = detectTvMode()
    document.documentElement.dataset.tv = String(tvMode.value)
    if (tvMode.value) {
      window.addEventListener('keydown', onKeydown)
      void nextTick(focusPageStart)
    }
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeydown)
    removeRouteHook()
    delete document.documentElement.dataset.tv
  })

  return { tvMode }
}
