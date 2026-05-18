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
      <div class="tools-content">
        <div class="tools-section">
          <h2>工具与插件管理</h2>
          <p class="section-desc">勾选 WorkerAgent 工具后点击"保存配置"。命令插件和容器插件可单独启停。</p>

          <div class="tool-list">
            <!-- Compose 组插件 -->
            <div class="tool-section-label" v-if="composes.length">
              <span class="section-icon">🎯</span> Compose 插件
            </div>
            <div
              v-for="comp in composes"
              :key="comp.name"
              class="compose-card"
            >
              <div class="compose-header">
                <div class="compose-title">
                  <span class="compose-icon">{{ getIcon(comp.icon) }}</span>
                  {{ comp.name }}
                  <span class="compose-status" :class="{ running: comp.running }">
                    {{ comp.running ? '● 运行中' : '○ 未启动' }}
                  </span>
                </div>
                <div class="compose-desc">{{ comp.description }}</div>
                <div class="compose-children" v-if="comp.children.length">
                  <span class="children-label">子工具:</span>
                  <code v-for="child in comp.children" :key="child.name">{{ child.name }}</code>
                </div>
                <div class="compose-actions">
                  <button
                    v-if="!comp.running"
                    class="action-btn start-btn"
                    :disabled="comp._starting"
                    @click="startCompose(comp)"
                  >
                    {{ comp._starting ? '启动中...' : '启动' }}
                  </button>
                  <template v-else>
                    <button class="action-btn stop-btn" :disabled="comp._stopping" @click="stopCompose(comp)">
                      {{ comp._stopping ? '停止中...' : '停止' }}
                    </button>
                    <button class="action-btn reset-btn" :disabled="comp._resetting" @click="resetCompose(comp)">
                      {{ comp._resetting ? '重置中...' : '重置' }}
                    </button>
                    <button class="action-btn regen-btn" :disabled="comp._regenerating" @click="regenCompose(comp)">
                      {{ comp._regenerating ? '生成中...' : '重新生成 Flag' }}
                    </button>
                  </template>
                </div>
              </div>
            </div>

            <!-- 命令型插件（非 WorkerAgent 工具） -->
            <div class="tool-section-label" v-if="commandPlugins.length">
              <span class="section-icon">📖</span> 命令插件
            </div>
            <div
              v-for="tool in commandPlugins"
              :key="tool.name"
              class="tool-card command-card"
            >
              <div class="tool-check command-indicator" :title="tool.description">
                <span>⌨</span>
              </div>
              <div class="tool-info">
                <div class="tool-name">
                  <span class="tool-icon">{{ getIcon(tool.icon) }}</span>
                  {{ tool.name }}
                  <span class="tool-badge" :class="tool.plugin_type">{{ tool.plugin_type }}</span>
                </div>
                <div class="tool-desc">{{ tool.description }}</div>
                <div class="tool-meta">
                  <template v-if="tool.plugin_type === 'exec'">
                    <span>容器: <code>{{ tool.container_name }}</code></span>
                    <span class="tool-status" :class="tool.status">
                      {{ tool.status === 'running' ? '运行中' : tool.status === 'stopped' ? '已停止' : '未启动' }}
                    </span>
                  </template>
                </div>
                <div class="tool-mounts" v-if="tool.mount_dirs && tool.mount_dirs.length">
                  挂载: <code v-for="dir in tool.mount_dirs" :key="dir">{{ dir }}</code>
                </div>
              </div>
              <div class="tool-actions" v-if="tool.plugin_type === 'exec'" @click.stop>
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

            <!-- WorkerAgent 工具 -->
            <div class="tool-section-label" v-if="workerTools.length">
              <span class="section-icon">⚙</span> WorkerAgent 工具
            </div>
            <div
              v-for="tool in workerTools"
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
                  <span class="tool-badge" :class="tool.plugin_type">{{ tool.plugin_type }}</span>
                </div>
                <div class="tool-desc">{{ tool.description }}</div>
                <div class="tool-meta">
                  <span>绑定动作: <code>{{ tool.bound_action }}</code></span>
                  <template v-if="tool.plugin_type === 'exec'">
                    <span>容器: <code>{{ tool.container_name }}</code></span>
                    <span class="tool-status" :class="tool.status">
                      {{ tool.status === 'running' ? '运行中' : tool.status === 'stopped' ? '已停止' : '未启动' }}
                    </span>
                  </template>
                </div>
                <div class="tool-mounts" v-if="tool.plugin_type === 'exec' && tool.mount_dirs && tool.mount_dirs.length">
                  挂载: <code v-for="dir in tool.mount_dirs" :key="dir">{{ dir }}</code>
                </div>
              </div>
              <div class="tool-actions" v-if="tool.plugin_type === 'exec'" @click.stop>
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
import { regenerateCompose } from '@/api/config'

const router = useRouter()

interface ToolPreset {
  name: string
  description: string
  plugin_type: string
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

const availableTools = ref<ToolPreset[]>([])
const selectedTools = ref<string[]>([])
const saving = ref(false)
const saved = ref(false)

interface ComposeItem {
  name: string
  description: string
  compose_file: string
  running: boolean
  category: string
  icon: string
  children: any[]
  _starting?: boolean
  _stopping?: boolean
  _resetting?: boolean
  _regenerating?: boolean
}

const composes = ref<ComposeItem[]>([])

const commandPlugins = computed(() =>
  availableTools.value.filter(t => t.plugin_type === 'command')
)

const workerTools = computed(() =>
  availableTools.value.filter(t => t.plugin_type !== 'command')
)

function getIcon(icon: string): string {
  const icons: Record<string, string> = {
    terminal: '⌘',
    search: '🔍',
    globe: '🌐',
    judge: '⚖️',
    book: '📖',
    target: '🎯',
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
    const [toolsResp, pluginsResp, composesResp] = await Promise.all([
      api.get('/agent/tools'),
      api.get('/plugins'),
      api.get('/composes'),
    ])
    const workerTools = toolsResp.data.available_tools || []
    const allPlugins = pluginsResp.data || []

    // WorkerAgent 工具列表（可勾选）
    availableTools.value = workerTools
    selectedTools.value = toolsResp.data.tool_names || []

    // 补充 command 类型插件（不可勾选为 WorkerAgent 工具，但可启停容器）
    const cmdPlugins = allPlugins.filter((p: any) => p.plugin_type === 'command')
    for (const cmd of cmdPlugins) {
      if (!availableTools.value.find((t: any) => t.name === cmd.name)) {
        availableTools.value.push(cmd)
      }
    }

    // Compose 组插件
    composes.value = (composesResp.data || []).map((c: any) => ({ ...c }))
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

async function startCompose(comp: ComposeItem) {
  comp._starting = true
  try {
    const resp = await api.post(`/plugins/${comp.name}/start`)
    if (resp.data.success) {
      comp.running = true
      // 重新加载配置以获取子工具
      await loadConfig()
    } else {
      alert(`启动失败: ${resp.data.message}`)
    }
  } catch (err: any) {
    alert(`启动失败: ${err.response?.data?.message || err.message}`)
  } finally {
    comp._starting = false
  }
}

async function stopCompose(comp: ComposeItem) {
  if (!confirm(`确定停止 "${comp.name}"？子工具将被注销。`)) return
  comp._stopping = true
  try {
    const resp = await api.post(`/plugins/${comp.name}/stop`)
    if (resp.data.success) {
      comp.running = false
      await loadConfig()
    } else {
      alert(`停止失败: ${resp.data.message}`)
    }
  } catch (err: any) {
    alert(`停止失败: ${err.response?.data?.message || err.message}`)
  } finally {
    comp._stopping = false
  }
}

async function resetCompose(comp: ComposeItem) {
  if (!confirm(`确定重置 "${comp.name}"？容器内数据将丢失！`)) return
  comp._resetting = true
  try {
    const resp = await api.post(`/plugins/${comp.name}/reset`)
    if (resp.data.success) {
      comp.running = true
      await loadConfig()
    } else {
      alert(`重置失败: ${resp.data.message}`)
    }
  } catch (err: any) {
    alert(`重置失败: ${err.response?.data?.message || err.message}`)
  } finally {
    comp._resetting = false
  }
}

async function regenCompose(comp: ComposeItem) {
  if (!confirm(`确定重新生成 Flag？旧 flag 将失效，环境将重建！`)) return
  comp._regenerating = true
  try {
    const result = await regenerateCompose(comp.name)
    if (result.success) {
      comp.running = true
      alert(`Flag 已重新生成！\n\n${result.message}`)
      await loadConfig()
    } else {
      alert(`生成失败: ${result.message}`)
    }
  } catch (err: any) {
    alert(`生成失败: ${err.response?.data?.message || err.message}`)
  } finally {
    comp._regenerating = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    // 1. 保存工具配置
    await api.post('/agent/tools', { tool_names: selectedTools.value })

    // 2. 自动启动已勾选的 exec 类型工具的容器
    const execToolsToStart = availableTools.value.filter(
      t => selectedTools.value.includes(t.name) && t.plugin_type === 'exec' && t.status !== 'running'
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

.tool-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 4px;
}

.section-icon {
  font-size: 14px;
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

.tool-card.command-card {
  background: rgba(230, 162, 60, 0.04);
  border-color: rgba(230, 162, 60, 0.15);
  cursor: default;
}

.tool-card.command-card:hover {
  background: rgba(230, 162, 60, 0.06);
  border-color: rgba(230, 162, 60, 0.25);
}

.command-indicator {
  color: #e6a23c;
  font-size: 16px;
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

.tool-badge.command {
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
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

.reset-btn {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
  border-color: rgba(230, 162, 60, 0.3);
}

.reset-btn:hover:not(:disabled) {
  background: rgba(230, 162, 60, 0.25);
}

.regen-btn {
  background: rgba(100, 60, 200, 0.15);
  color: #b37feb;
  border-color: rgba(100, 60, 200, 0.3);
}

.regen-btn:hover:not(:disabled) {
  background: rgba(100, 60, 200, 0.25);
}

/* Compose 卡片 */
.compose-card {
  background: rgba(100, 60, 200, 0.06);
  border: 1px solid rgba(100, 60, 200, 0.2);
  border-radius: 10px;
  padding: 14px 16px;
  transition: all 0.2s;
}

.compose-card:hover {
  border-color: rgba(100, 60, 200, 0.35);
}

.compose-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.compose-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.compose-icon {
  font-size: 16px;
}

.compose-status {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 4px;
  background: rgba(108, 117, 125, 0.2);
  color: rgba(255, 255, 255, 0.5);
}

.compose-status.running {
  background: rgba(40, 167, 69, 0.2);
  color: #7bdd8a;
}

.compose-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  white-space: pre-line;
}

.compose-children {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  flex-wrap: wrap;
}

.children-label {
  font-weight: 500;
}

.compose-children code {
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'Fira Code', monospace;
}

.compose-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
