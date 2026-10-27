import { createRouter, createWebHistory } from 'vue-router'

import HomePage from '../pages/HomePage.vue'
import LibraryPage from '../pages/LibraryPage.vue'
import CatalogPage from '../pages/CatalogPage.vue'
import CreditsPage from '../pages/CreditsPage.vue'
import DownloadsPage from '../pages/DownloadsPage.vue'
import MediaDetailsPage from '../pages/MediaDetailsPage.vue'
import SearchPage from '../pages/SearchPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', name: 'home', component: HomePage },
    { path: '/movies', name: 'movies', component: CatalogPage, meta: { kind: 'movie' } },
    { path: '/series', name: 'series', component: CatalogPage, meta: { kind: 'series' } },
    { path: '/movies/:id', name: 'movie-details', component: MediaDetailsPage, meta: { kind: 'movie' } },
    { path: '/series/:id', name: 'series-details', component: MediaDetailsPage, meta: { kind: 'series' } },
    { path: '/search', name: 'search', component: SearchPage },
    { path: '/credits', name: 'credits', component: CreditsPage },
    { path: '/library', name: 'library', component: LibraryPage },
    { path: '/downloads', name: 'downloads', component: DownloadsPage },
  ],
})

