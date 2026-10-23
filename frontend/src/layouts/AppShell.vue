<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand focus-ring" to="/" aria-label="KADR — главная">KADR</RouterLink>
      <nav aria-label="Основная навигация">
        <RouterLink class="nav-link focus-ring" to="/">Главная</RouterLink>
      </nav>
    </header>
    <main>
      <slot />
    </main>
  </div>
</template>

