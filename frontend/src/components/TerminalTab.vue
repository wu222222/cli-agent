<template>
  <div class="terminal-tab">
    <div class="term-header">
      <span class="term-title">终端</span>
      <select v-model="selectedContainer" class="term-select" @change="connectTerminal">
        <option value="">选择容器...</option>
        <option v-for="c in runningContainers" :key="c.name" :value="c.name">
          {{ c.name }}
        </option>
      </select>
    </div>

    <div v-if="!selectedContainer" class="term-empty">
      <div class="term-empty-icon">>_</div>
      <div>选择一个已启动的容器</div>
      <small>在工具设置页面启动容器后可在这里连接</small>
    </div>

    <div v-else ref="terminalContainer" class="term-container"></div>

    <div v-if="connected" class="term-status">
      <span class="term-status-dot connected"></span>
      <span>{{ selectedContainer }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
import api from '@/api/agent'

interface ContainerInfo {
  name: string
  status: string
}

const runningContainers = ref<ContainerInfo[]>([])
const selectedContainer = ref('')
const connected = ref(false)
const terminalContainer = ref<HTMLElement | null>(null)

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let ws: WebSocket | null = null

async function loadContainers() {
  try {
    const resp = await api.get('/plugins')
    const plugins = resp.data || []
    runningContainers.value = plugins
      .filter((p: any) => p.status === 'running' && p.plugin_type === 'exec')
      .map((p: any) => ({
        name: p.container_name || p.name,
        status: p.status,
      }))
  } catch {
    runningContainers.value = []
  }
}

function initTerminal() {
  if (!terminalContainer.value) return

  terminal = new Terminal({
    theme: {
      background: '#1a1b23',
      foreground: '#e0e0e0',
      cursor: '#409eff',
      selectionBackground: 'rgba(64, 158, 255, 0.3)',
    },
    fontSize: 13,
    fontFamily: "'Consolas', 'Monaco', monospace",
    cursorBlink: true,
    scrollback: 1000,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalContainer.value)
  fitAddon.fit()

  // 监听用户输入
  terminal.onData((data: string) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(new TextEncoder().encode(data))
    }
  })

  // 监听窗口大小变化
  const resizeObserver = new ResizeObserver(() => {
    fitAddon?.fit()
  })
  resizeObserver.observe(terminalContainer.value)
}

function connectTerminal() {
  if (!selectedContainer.value) return

  // 断开旧连接
  disconnectTerminal()

  nextTick(() => {
    initTerminal()
    if (!terminal) return

    // 连接 WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/terminal/${selectedContainer.value}`
    console.log('[Terminal] 连接 WebSocket:', url)
    ws = new WebSocket(url)

    ws.onopen = () => {
      console.log('[Terminal] WebSocket 已连接')
      connected.value = true
      terminal?.writeln('\x1b[32m✓ 已连接到 ' + selectedContainer.value + '\x1b[0m')
    }

    ws.onmessage = (event) => {
      console.log('[Terminal] 收到消息:', event.data)
      if (event.data instanceof Blob) {
        event.data.arrayBuffer().then((buffer) => {
          terminal?.write(new Uint8Array(buffer))
        })
      } else {
        terminal?.write(event.data)
      }
    }

    ws.onclose = (event) => {
      console.log('[Terminal] WebSocket 关闭:', event.code, event.reason)
      connected.value = false
      terminal?.writeln('\r\n\x1b[31m✗ 连接已断开\x1b[0m')
    }

    ws.onerror = (error) => {
      console.error('[Terminal] WebSocket 错误:', error)
      connected.value = false
      terminal?.writeln('\r\n\x1b[31m✗ 连接错误\x1b[0m')
    }
  })
}

function disconnectTerminal() {
  if (ws) {
    ws.close()
    ws = null
  }
  if (terminal) {
    terminal.dispose()
    terminal = null
  }
  fitAddon = null
  connected.value = false
}

// 切换会话时刷新容器列表
watch(() => selectedContainer.value, () => {
  if (!selectedContainer.value) {
    disconnectTerminal()
  }
})

onMounted(() => {
  loadContainers()
})

onBeforeUnmount(() => {
  disconnectTerminal()
})

defineExpose({ loadContainers })
</script>

<style scoped>
.terminal-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.term-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #2d2e3a;
}

.term-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
  flex-shrink: 0;
}

.term-select {
  flex: 1;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
  outline: none;
  cursor: pointer;
}

.term-select:focus {
  border-color: rgba(64, 158, 255, 0.5);
}

.term-select option {
  background: #1a1b23;
  color: #e0e0e0;
}

.term-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 13px;
  gap: 8px;
}

.term-empty-icon {
  font-size: 32px;
  color: #409eff;
  font-family: monospace;
  opacity: 0.5;
}

.term-empty small {
  color: #555;
  font-size: 11px;
}

.term-container {
  flex: 1;
  padding: 4px;
  overflow: hidden;
}

.term-container :deep(.xterm) {
  height: 100%;
}

.term-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-top: 1px solid #2d2e3a;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.term-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #666;
}

.term-status-dot.connected {
  background: #22c55e;
}
</style>
