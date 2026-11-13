<script setup lang="ts">
import { useRouter } from 'vue-router'

import GlobalSearch from '../components/GlobalSearch.vue'
import TmdbCredit from '../components/TmdbCredit.vue'
import { useTvNavigation } from '../composables/useTvNavigation'

const router = useRouter()
const { tvMode } = useTvNavigation(router)
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand focus-ring" to="/" aria-label="KADR — главная">KADR</RouterLink>
      <nav aria-label="Основная навигация">
        <RouterLink class="nav-link focus-ring" to="/">Главная</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/movies">Фильмы</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/series">Сериалы</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/new">Новинки</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/cartoons">Мультфильмы</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/history">Продолжить просмотр</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/library">Библиотека</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/downloads">Загрузки</RouterLink>
      </nav>
      <GlobalSearch />
      <span v-if="tvMode" class="tv-mode-badge" aria-label="Включён режим телевизора">TV</span>
    </header>
    <main>
      <slot />
    </main>
    <TmdbCredit />
  </div>
</template>

