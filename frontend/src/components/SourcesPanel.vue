<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { friendlyApiError, getSources } from '../services/api'
import type { MediaKind, SourceRelease, SourceSort } from '../types/media'
import StatePanel from './StatePanel.vue'

const props = defineProps<{ mediaId: number; kind: MediaKind }>()
const items = ref<SourceRelease[]>([])
const query = ref('')
const loading = ref(false)
const error = ref('')
const searched = ref(false)
const sort = ref<SourceSort>('seeders')
const order = computed(() => (sort.value === 'title' ? 'asc' : 'desc'))

function formatBytes(bytes: number): string {
  if (bytes <= 0) return 'Размер неизвестен'
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

async function loadSources(): Promise<void> {
  loading.value = true
  searched.value = true
  error.value = ''
  try {
    const result = await getSources(props.mediaId, props.kind, sort.value, order.value)
    items.value = result.items
    query.value = result.query
  } catch (caught) {
    items.value = []
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

watch(sort, () => {
  if (searched.value) void loadSources()
})
</script>

<template>
  <section class="details-section sources-section">
    <div class="sources-heading">
      <div>
        <p class="eyebrow">Prowlarr</p>
        <h2>Доступные источники</h2>
      </div>
      <label v-if="searched" class="source-sort">
        <span>Сортировка</span>
        <select v-model="sort">
          <option value="seeders">По сидам</option>
          <option value="resolution">По разрешению</option>
          <option value="source">По источнику</option>
          <option value="size">По размеру</option>
          <option value="title">По названию</option>
        </select>
      </label>
    </div>

    <div v-if="!searched" class="source-intro">
      <p>Поиск выполняется вручную через настроенные индексаторы и может занять несколько секунд.</p>
      <button class="button primary focus-ring" type="button" @click="loadSources">
        Найти источники
      </button>
    </div>
    <div v-else-if="loading" class="source-loading" role="status">Ищем доступные релизы…</div>
    <StatePanel
      v-else-if="error"
      title="Поиск источников недоступен"
      :message="error"
      show-retry
      @retry="loadSources"
    />
    <StatePanel
      v-else-if="items.length === 0"
      title="Релизы не найдены"
      :message="`По запросу «${query}» настроенные индексаторы ничего не вернули.`"
      show-retry
      @retry="loadSources"
    />
    <div v-else class="source-results">
      <p class="source-summary">Найдено: {{ items.length }} · запрос «{{ query }}»</p>
      <article v-for="item in items" :key="item.id" class="source-release">
        <div class="source-release-main">
          <h3>{{ item.title }}</h3>
          <p>{{ item.indexer }} · {{ formatBytes(item.size_bytes) }}</p>
          <div class="release-tags">
            <span v-if="item.resolution">{{ item.resolution }}</span>
            <span v-if="item.source">{{ item.source }}</span>
            <span v-if="item.codec">{{ item.codec }}</span>
            <span v-if="item.hdr_format">{{ item.hdr_format }}</span>
            <span v-if="item.audio">{{ item.audio }}</span>
            <span v-if="item.language">{{ item.language }}</span>
            <span v-if="item.release_type">{{ item.release_type }}</span>
          </div>
        </div>
        <dl class="source-health">
          <div><dt>Сиды</dt><dd>{{ item.seeders ?? '—' }}</dd></div>
          <div><dt>Пиры</dt><dd>{{ item.peers ?? '—' }}</dd></div>
        </dl>
      </article>
      <p class="source-stage-note">Выбор и загрузка релиза появятся на этапе 4.</p>
    </div>
  </section>
</template>
