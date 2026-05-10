import { reactive } from 'vue'
import { getPlugins, startPlugin, stopPlugin } from '@/api/config'
import type { PluginDetail } from '@/types'

function getPluginStatus(name: string): string {
  const plugin = store.plugins.find(p => p.name === name)
  return plugin?.status || 'unknown'
}

function getPluginType(name: string): string {
  const plugin = store.plugins.find(p => p.name === name)
  return plugin?.tool_type || ''
}

async function fetchPlugins() {
  try {
    store.plugins = await getPlugins()
  } catch (err) {
    console.error('Failed to fetch plugins:', err)
  }
}

async function start(name: string) {
  store.loading[name] = true
  try {
    await startPlugin(name)
    await fetchPlugins()
  } catch (err) {
    console.error(`Failed to start plugin ${name}:`, err)
  } finally {
    store.loading[name] = false
  }
}

async function stop(name: string) {
  store.loading[name] = true
  try {
    await stopPlugin(name)
    await fetchPlugins()
  } catch (err) {
    console.error(`Failed to stop plugin ${name}:`, err)
  } finally {
    store.loading[name] = false
  }
}

async function togglePlugin(name: string) {
  const status = getPluginStatus(name)
  if (status === 'running') {
    await stop(name)
  } else {
    await start(name)
  }
}

const store = reactive({
  plugins: [] as PluginDetail[],
  loading: {} as Record<string, boolean>,
  activeFilter: 'all',
  get filteredPlugins(): PluginDetail[] {
    if (store.activeFilter === 'all') return store.plugins
    return store.plugins.filter(p => p.tool_type === store.activeFilter)
  },
  getPluginStatus,
  getPluginType,
  fetchPlugins,
  start,
  stop,
  togglePlugin
})

export function usePluginStore() {
  return store
}
