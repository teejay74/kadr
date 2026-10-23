<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getHealth, type HealthResponse } from '../services/api'

const health = ref<HealthResponse | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    health.value = await getHealth()
  } catch {
    error.value = 'API пока недоступен'
  }
})
</script>

<template>
  <section class="hero">
    <p class="eyebrow">Персональная медиаплатформа</p>
    <h1>Кино начинается с&nbsp;кадра.</h1>
    <p class="lead">
      Базовая платформа готова. Каталог, источники и воспроизведение появятся на следующих этапах.
    </p>
    <div class="status-card" aria-live="polite">
      <span class="status-dot" :class="{ ready: health?.status === 'ok' }" />
      <span v-if="health">Система работает · API {{ health.version }} · SQLite подключена</span>
      <span v-else-if="error">{{ error }}</span>
      <span v-else>Проверяем состояние системы…</span>
    </div>
  </section>
</template>

