<template>
  <div class="tool-card" :class="[`tool-${props.toolState.toolName}`, `status-${props.toolState.status}`]">
    <div class="tool-card-header" @click="toggleExpand">
      <span class="tool-icon">{{ toolIcon }}</span>
      <span class="tool-name">{{ displayName }}</span>
      <span class="tool-status">
        <span v-if="props.toolState.status === 'running'" class="status-dot running"></span>
        <span v-else-if="props.toolState.status === 'completed'" class="status-dot completed">✓</span>
        <span v-else class="status-dot error">✗</span>
      </span>
      <span v-if="props.toolState.status === 'running'" class="tool-time">{{ elapsedTime }}</span>
      <span v-else-if="duration" class="tool-time">{{ duration }}</span>
      <span v-if="collapsible && hasContent" class="expand-icon">{{ expanded ? '▾' : '▸' }}</span>
    </div>
    <div v-if="expanded || !collapsible" class="tool-card-body">
      <div v-if="props.toolState.status === 'running'" class="tool-running">
        <span class="spinner"></span>
        <span>{{ props.toolState.startContent }}</span>
      </div>
      <div v-else-if="props.toolState.status === 'completed' && props.toolState.resultContent" class="tool-result">
        <pre>{{ props.toolState.resultContent }}</pre>
      </div>
      <div v-else-if="props.toolState.status === 'error'" class="tool-error">
        <pre>{{ props.toolState.resultContent || '执行出错' }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { ToolCardState } from '@/types'

const props = withDefaults(defineProps<{
  toolState: ToolCardState
  collapsible?: boolean
}>(), {
  collapsible: true,
})

const expanded = ref(props.toolState.status !== 'completed')

const hasContent = computed(() => {
  return props.toolState.startContent || props.toolState.resultContent
})

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  search: '网络搜索',
  call_judge: 'Judge 评审',
}

const TOOL_ICONS: Record<string, string> = {
  search: '🌐',
  call_judge: '⚖',
}

const displayName = computed(() => {
  return TOOL_DISPLAY_NAMES[props.toolState.toolName] || props.toolState.toolName
})

const toolIcon = computed(() => {
  return TOOL_ICONS[props.toolState.toolName] || '⚙'
})

const startTimeMs = computed(() => new Date(props.toolState.startTime).getTime())

const duration = ref('')

const elapsedTime = ref('')

let timer: ReturnType<typeof setInterval> | null = null

function updateElapsed() {
  const diff = Date.now() - startTimeMs.value
  elapsedTime.value = formatDuration(diff)
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const remainS = Math.floor(s % 60)
  return `${m}m${remainS}s`
}

function toggleExpand() {
  if (props.collapsible) {
    expanded.value = !expanded.value
  }
}

onMounted(() => {
  if (props.toolState.status === 'running') {
    timer = setInterval(updateElapsed, 100)
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

watch(() => props.toolState.status, (newStatus) => {
  if (newStatus !== 'running' && timer) {
    clearInterval(timer)
    timer = null
    const diff = Date.now() - startTimeMs.value
    duration.value = formatDuration(diff)
    if (props.collapsible) {
      expanded.value = true
    }
  }
})
</script>

<style scoped>
.tool-card {
  border-radius: 8px;
  margin: 4px 0;
  overflow: hidden;
  border-left: 3px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.03);
}

.tool-search {
  border-left-color: #e6a23c;
}

.tool-call_judge {
  border-left-color: #f56c6c;
}

.tool-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}

.tool-card-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tool-icon {
  font-size: 16px;
}

.tool-name {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.tool-status {
  margin-left: auto;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.running {
  background: #409eff;
  animation: pulse 1.2s ease-in-out infinite;
}

.status-dot.completed {
  color: #67c23a;
  font-size: 12px;
  width: auto;
  height: auto;
  border-radius: 0;
}

.status-dot.error {
  color: #f56c6c;
  font-size: 12px;
  width: auto;
  height: auto;
  border-radius: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.tool-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  font-family: monospace;
}

.expand-icon {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.tool-card-body {
  padding: 0 12px 8px;
}

.tool-running {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(64, 158, 255, 0.3);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tool-result pre {
  margin: 0;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.85);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.tool-error pre {
  margin: 0;
  padding: 8px 12px;
  background: rgba(245, 108, 108, 0.1);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #f56c6c;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
