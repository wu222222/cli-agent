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

router.beforeEach(async (to, _from, next) => {
  // 已检查过且已配置，直接放行
  if (setupChecked && isConfigured) return next()
  // 已在 setup 页面，放行
  if (to.path === '/setup') return next()

  // 未检查过，尝试检测
  if (!setupChecked) {
    try {
      const resp = await fetch('/api/setup/status')
      const data = await resp.json()
      setupChecked = true
      isConfigured = data.configured
      if (!isConfigured) {
        return next('/setup')
      }
    } catch {
      // 后端未就绪，放行（让页面自己处理）
      setupChecked = true
      isConfigured = true
    }
  }

  next()
})

export default router