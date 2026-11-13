<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { searchMedia } from '../services/api'
import type { MediaCardData } from '../types/media'

const route = useRoute()
const router = useRouter()
const query = ref('')
const term = computed(() => query.value.trim())
const input = ref<HTMLInputElement | null>(null)
const form = ref<HTMLFormElement | null>(null)
const open = ref(false)
const active = ref(-1)
const items = ref<MediaCardData[]>([])
const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const expanded = computed(() => open.value && term.value.length >= 2)

watch(() => route.fullPath, () => {
  close()
  query.value = typeof route.query.q === 'string' && route.name === 'search'
    ? route.query.q.slice(0, 100)
    : ''
}, { immediate: true })

watch([term, expanded], ([value, visible], _, onCleanup) => {
  active.value = -1
  items.value = []
  status.value = visible ? 'loading' : 'idle'
  if (!visible) return
  const controller = new AbortController()
  const timer = window.setTimeout(async () => {
    const [movieResult, seriesResult] = await Promise.allSettled([
      searchMedia('movie', value, 1, controller.signal),
      searchMedia('series', value, 1, controller.signal),
    ])
    if (controller.signal.aborted) return
    const movies = movieResult.status === 'fulfilled' ? movieResult.value.items : []
    const series = seriesResult.status === 'fulfilled' ? seriesResult.value.items : []
    const mixed = movies.flatMap((movie, index) => {
      const show = series[index]
      return show ? [movie, show] : [movie]
    })
    mixed.push(...series.slice(movies.length))
    const needle = value.toLowerCase()
    items.value = mixed.sort((left, right) => matchRank(left, needle) - matchRank(right, needle)).slice(0, 12)
    status.value = !items.value.length && (movieResult.status === 'rejected' || seriesResult.status === 'rejected')
      ? 'error'
      : 'ready'
  }, 400)
  onCleanup(() => {
    window.clearTimeout(timer)
    controller.abort()
  })
}, { flush: 'sync' })

function matchRank(item: MediaCardData, needle: string): number {
  const titles = [item.title, item.original_title].map((title) => title.toLowerCase())
  if (titles.includes(needle)) return 0
  if (titles.some((title) => title.startsWith(needle))) return 1
  if (titles.some((title) => title.includes(needle))) return 2
  return 3
}

function label(item: MediaCardData): string {
  const original = item.original_title.trim()
  const title = original && original.toLowerCase() !== item.title.toLowerCase()
    ? `${item.title} / ${original}`
    : item.title
  return item.year ? `${title} (${item.year})` : title
}

function parts(text: string): string[] {
  const literal = term.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return literal ? text.split(new RegExp(`(${literal})`, 'giu')) : [text]
}

function close(): void {
  open.value = false
}

function clear(): void {
  query.value = ''
  input.value?.focus()
}

function leave(event: FocusEvent): void {
  if (!(event.relatedTarget instanceof Node) || !form.value?.contains(event.relatedTarget)) close()
}

function move(event: KeyboardEvent, step: number): void {
  if (event.isComposing || term.value.length < 2) return
  event.preventDefault()
  open.value = true
  if (!items.value.length) return
  const next = active.value < 0 ? (step > 0 ? 0 : items.value.length - 1) : active.value + step
  active.value = (next + items.value.length) % items.value.length
  void nextTick(() => document.getElementById(`search-option-${active.value}`)?.scrollIntoView?.({ block: 'nearest' }))
}

function escape(event: KeyboardEvent): void {
  if (!expanded.value || event.isComposing) return
  event.preventDefault()
  event.stopPropagation()
  close()
}

function select(item: MediaCardData): void {
  close()
  query.value = ''
  input.value?.blur()
  void router.push({ name: item.kind === 'movie' ? 'movie-details' : 'series-details', params: { id: item.id } })
}

function submit(): void {
  const selected = expanded.value ? items.value[active.value] : undefined
  if (selected) {
    select(selected)
  } else if (term.value.length >= 2) {
    close()
    void router.push({ name: 'search', query: { q: term.value } })
  }
}
</script>

<template>
  <form ref="form" class="global-search" role="search" @submit.prevent="submit" @focusout="leave">
    <label class="sr-only" for="global-search">Поиск фильмов и сериалов</label>
    <div class="search-input">
      <input
        id="global-search"
        ref="input"
        v-model="query"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="expanded"
        :aria-controls="expanded ? 'search-suggestions' : undefined"
        :aria-activedescendant="active >= 0 ? `search-option-${active}` : undefined"
        maxlength="100"
        autocomplete="off"
        placeholder="Найти…"
        @focus="open = true"
        @click="open = true"
        @input="open = true"
        @keydown.down="move($event, 1)"
        @keydown.up="move($event, -1)"
        @keydown.esc="escape"
      />
      <button v-if="query" type="button" class="search-clear focus-ring" aria-label="Очистить поиск" @click="clear">×</button>
    </div>
    <div v-if="expanded" class="search-popup">
      <ul id="search-suggestions" role="listbox" aria-label="Подсказки поиска">
        <li
          v-for="(item, index) in items"
          :id="`search-option-${index}`"
          :key="`${item.kind}-${item.id}`"
          role="option"
          :aria-selected="active === index"
          @mousedown.prevent
          @click="select(item)"
        >
          <template v-for="(part, partIndex) in parts(label(item))" :key="partIndex">
            <mark v-if="partIndex % 2">{{ part }}</mark><template v-else>{{ part }}</template>
          </template>
        </li>
      </ul>
      <p v-if="status === 'loading'" role="status">Ищем…</p>
      <p v-else-if="status === 'error'" role="status">Подсказки недоступны. Нажмите Enter, чтобы повторить поиск.</p>
      <p v-else-if="!items.length" role="status">Совпадений нет</p>
    </div>
  </form>
</template>
