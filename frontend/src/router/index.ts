import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue')
  },
  {
    path: '/setup',
    name: 'Setup',
    component: () => import('@/views/SetupView.vue')
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/HistoryView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue')
  },
  {
    path: '/tools',
    name: 'Tools',
    component: () => import('@/views/ToolsView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 首次启动引导守卫
let setupChecked = false
let isConfigured = false

export function markConfigured() {
  isConfigured = true
  setupChecked = true
}

router.beforeEach(async (to, _from, next) => {
  if (to.path === '/setup') return next()
  if (setupChecked && isConfigured) return next()

  if (!setupChecked) {
    try {
      const resp = await fetch('/api/setup/status')
      const data = await resp.json()
      setupChecked = true
      isConfigured = data.configured
    } catch {
      setupChecked = true
      isConfigured = true
    }
  }

  if (!isConfigured) return next('/setup')
  next()
})

export default router