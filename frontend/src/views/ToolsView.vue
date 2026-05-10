<template>
  <div class="tools-container">
    <header class="tools-header">
      <div class="header-left">
        <button class="back-btn" @click="$router.push('/')">← 返回</button>
        <h1>工具设置</h1>
      </div>
      <div class="header-right">
        <span class="status-text" v-if="saved">已保存</span>
        <button class="save-btn" @click="saveConfig" :disabled="saving">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </header>

    <div class="tools-body">
      <!-- Agent 选择 -->
      <div class="agent-tabs">
        <button
          v-for="agent in agents"
          :key="agent.id"
          :class="['agent-tab', { active: activeAgent === agent.id }]"
          @click="activeAgent = agent.id"
        >
          {{ agent.name }}
        </button>
      </div>

      <div class="tools-content">
        <div class="tools-section">
          <h2>{{ currentAgentName }} 的工具</h2>
          <p class="section-desc">勾选工具后点击"保存配置"，立即生效。</p>

          <div class="tool-list">
            <div
              v-for="tool in availableTools"
              :key="tool.name"
              class="tool-card"
              :class="{ selected: selectedTools.includes(tool.name) }"
              @click="toggleTool(tool.name)"
            >
              <div class="tool-check">
                <span v-if="selectedTools.includes(tool.name)">✅</span>
                <span v-else>☐</span>
              </div>
              <div class="tool-info">
                <div class="tool-name">
                  <span class="tool-icon">{{ getIcon(tool.icon) }}</span>
                  {{ tool.name }}
                  <span class="tool-badge" :class="tool.tool_type">{{ tool.tool_type }}</span>
                </div>
                <div class="tool-desc">{{ tool.description }}</div>
                <div class="tool-meta">
                  <span>绑定动作: <code>{{ tool.bound_action }}</code></span>
                  <template v-if="tool.tool_type === 'exec'">
                    <span>容器: <code>{{ tool.container_name }}</code></span>
                    <span class="tool-status" :class="tool.status">
                      {{ tool.status === 'running' ? '运行中' : tool.status === 'stopped' ? '已停止' : '未启动' }}
                    </span>
                  </template>
                </div>
                <div class="tool-mounts" v-if="tool.tool_type === 'exec' && tool.mount_dirs && tool.mount_dirs.length">
                  挂载: <code v-for="dir in tool.mount_dirs" :key="dir">{{ dir }}</code>
                </div>
              </div>
              <div class="tool-actions" v-if="tool.tool_type === 'exec'" @click.stop>
                <button
                  v-if="tool.status !== 'running'"
                  class="action-btn start-btn"
                  :disabled="tool._starting"
                  @click="startContainer(tool)"
                >
                  {{ tool._starting ? '启动中...' : '启动' }}
                </button>
                <button
                  v-else
                  class="action-btn stop-btn"
                  :disabled="tool._stopping"
                  @click="stopContainer(tool)"
                >
                  {{ tool._stopping ? '停止中...' : '停止' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/agent'

const router = useRouter()

interface ToolPreset {
  name: string
  description: string
  tool_type: string
  container_name: string
  status: string
  bound_action: string
  requires_confirmation: boolean
  mount_dirs: string[]
  category: string
  icon: string
  _starting?: boolean
  _stopping?: boolean
}

const agents = [
  { id: 'worker', name: 'WorkerAgent' },
]

const activeAgent = ref('worker')
const availableTools = ref<ToolPreset[]>([])
const selectedTools = ref<string[]>([])
const saving = ref(false)
const saved = ref(false)

const currentAgentName = computed(() => {
  return agents.find(a => a.id === activeAgent.value)?.name || 'Agent'
})

function getIcon(icon: string): string {
  const icons: Record<string, string> = {
    terminal: '⌘',
    search: '🔍',
    globe: '🌐',
    judge: '⚖️',
    default: '📦',
  }
  return icons[icon] || icons.default
}

function toggleTool(name: string) {
  const idx = selectedTools.value.indexOf(name)
  if (idx >= 0) {
    selectedTools.value.splice(idx, 1)
  } else {
    selectedTools.value.push(name)
  }
  saved.value = false
}

async function loadConfig() {
  try {
    const resp = await api.get('/agent/tools')
    availableTools.value = resp.data.available_tools || []
    selectedTools.value = resp.data.tool_names || []
  } catch (err) {
    console.error('Failed to load tools config:', err)
  }
}

async function startContainer(tool: ToolPreset) {
  tool._starting = true
  try {
    const resp = await api.post(`/plugins/${tool.name}/start`)
    if (resp.data.success) {
      tool.status = 'running'
    } else {
      alert(`启动失败: ${resp.data.message}`)
    }
  } catch (err: any) {
    alert(`启动失败: ${err.response?.data?.message || err.message}`)
  } finally {
    tool._starting = false
  }
}

async function stopContainer(tool: ToolPreset) {
  tool._stopping = true
  try {
    const resp = await api.post(`/plugins/${tool.name}/stop`)
    if (resp.data.success) {
      tool.status = 'stopped'
    } else {
      alert(`停止失败: ${resp.data.message}`)
    }
  } catch (err: any) {
    alert(`停止失败: ${err.response?.data?.message || err.message}`)
  } finally {
    tool._stopping = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    // 1. 保存工具配置
    await api.post('/agent/tools', { tool_names: selectedTools.value })

    // 2. 自动启动已勾选的 exec 类型工具的容器
    const execToolsToStart = availableTools.value.filter(
      t => selectedTools.value.includes(t.name) && t.tool_type === 'exec' && t.status !== 'running'
    )
    for (const tool of execToolsToStart) {
      try {
        const resp = await api.post(`/plugins/${tool.name}/start`)
        if (resp.data.success) {
          tool.status = 'running'
        }
      } catch (e) {
        console.warn(`自动启动容器 ${tool.name} 失败:`, e)
      }
    }

    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (err) {
    console.error('Failed to save tools config:', err)
    alert('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.tools-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: rgba(255, 255, 255, 0.9);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.tools-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.back-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-text {
  color: #67c23a;
  font-size: 13px;
}

.save-btn {
  padding: 8px 20px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.save-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.save-btn:disabled {
  background: rgba(64, 158, 255, 0.5);
  cursor: not-allowed;
}

.tools-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agent-tabs {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.agent-tab {
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: transparent;
  color: rgba(255, 255, 255, 0.6);
  transition: all 0.2s;
}

.agent-tab:hover {
  border-color: rgba(255, 255, 255, 0.25);
  color: rgba(255, 255, 255, 0.8);
}

.agent-tab.active {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.12);
  color: #79bbff;
}

.tools-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.tools-section h2 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
}

.section-desc {
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  margin: 0 0 16px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-card {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.15);
}

.tool-card.selected {
  background: rgba(64, 158, 255, 0.08);
  border-color: rgba(64, 158, 255, 0.3);
}

.tool-check {
  font-size: 18px;
  width: 24px;
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

.tool-info {
  flex: 1;
}

.tool-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.tool-icon {
  font-size: 15px;
}

.tool-badge {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
}

.tool-badge.exec {
  background: rgba(0, 123, 255, 0.2);
  color: #6cb2ff;
}

.tool-badge.local {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.tool-badge.network {
  background: rgba(40, 167, 69, 0.2);
  color: #7bdd8a;
}

.tool-desc {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  margin-bottom: 4px;
}

.tool-meta {
  color: rgba(255, 255, 255, 0.4);
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-meta code {
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'Fira Code', monospace;
}

.tool-mounts {
  color: rgba(255, 255, 255, 0.4);
  font-size: 11px;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tool-mounts code {
  background: rgba(255, 193, 7, 0.12);
  color: #ffc107;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-family: 'Fira Code', monospace;
}

.tool-status {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
}

.tool-status.running {
  background: rgba(40, 167, 69, 0.2);
  color: #7bdd8a;
}

.tool-status.stopped {
  background: rgba(220, 53, 69, 0.2);
  color: #f08080;
}

.tool-status.unknown {
  background: rgba(108, 117, 125, 0.2);
  color: rgba(255, 255, 255, 0.5);
}

.tool-actions {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

.action-btn {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.start-btn {
  background: rgba(40, 167, 69, 0.15);
  color: #7bdd8a;
  border-color: rgba(40, 167, 69, 0.3);
}

.start-btn:hover:not(:disabled) {
  background: rgba(40, 167, 69, 0.25);
}

.stop-btn {
  background: rgba(220, 53, 69, 0.15);
  color: #f08080;
  border-color: rgba(220, 53, 69, 0.3);
}

.stop-btn:hover:not(:disabled) {
  background: rgba(220, 53, 69, 0.25);
}
</style>
