<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import TmdbCredit from '../components/TmdbCredit.vue'

const router = useRouter()
const search = ref('')

function submitSearch(): void {
  const query = search.value.trim()
  if (query.length >= 2) {
    void router.push({ name: 'search', query: { q: query } })
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand focus-ring" to="/" aria-label="KADR — главная">KADR</RouterLink>
      <nav aria-label="Основная навигация">
        <RouterLink class="nav-link focus-ring" to="/">Главная</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/movies">Фильмы</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/series">Сериалы</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/library">Библиотека</RouterLink>
        <RouterLink class="nav-link focus-ring" to="/downloads">Загрузки</RouterLink>
      </nav>
      <form class="global-search" role="search" @submit.prevent="submitSearch">
        <label class="sr-only" for="global-search">Поиск фильмов и сериалов</label>
        <input id="global-search" v-model="search" minlength="2" placeholder="Найти…" />
      </form>
    </header>
    <main>
      <slot />
    </main>
    <TmdbCredit />
  </div>
</template>

