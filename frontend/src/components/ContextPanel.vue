<template>
  <div class="context-panel-wrapper" :class="{ collapsed: isCollapsed }" :style="{ width: isCollapsed ? '0' : panelWidth + 'px' }">
    <!-- 拖拽调整条 -->
    <div
      class="resize-handle"
      @mousedown="onResizeStart"
      title="拖拽调整宽度"
    ></div>

    <div class="context-panel">
      <div class="context-panel-header">
        <span class="context-panel-title">上下文</span>
        <button class="clear-btn" @click="clearContext" title="清空上下文">清空</button>
      </div>
      <div class="context-panel-stats">
        Step {{ ctxStatus.step }} | ~{{ ctxStatus.total_count * 200 }} tok | {{ ctxStatus.total_count }} 条
        <span v-if="ctxStatus.summary_count" class="ctx-summary-badge">{{ ctxStatus.summary_count }} 摘要</span>
      </div>
      <div class="context-panel-policy">
        衰减: 完整{{ ctxStatus.policy?.tool_full_turns }} / 截断{{ ctxStatus.policy?.tool_truncate_turns }} / 遗忘{{ ctxStatus.policy?.tool_max_turns }}
      </div>
      <div class="context-panel-list">
        <div
          v-for="(msg, idx) in ctxStatus.messages"
          :key="idx"
          class="context-msg"
          :class="[`ctx-stage-${msg.stage}`, { expanded: expandedMsgs.has(idx) }]"
          @click="toggleMsg(idx)"
        >
          <span class="ctx-stage-icon">{{ stageIcon(msg.stage) }}</span>
          <span class="ctx-role">{{ msg.role }}</span>
          <span class="ctx-sender">{{ msg.tool_name || msg.sender }}</span>
          <span class="ctx-age">age:{{ msg.age }}</span>
          <span class="ctx-preview">{{ msg.preview }}</span>
          <span class="ctx-len">{{ msg.content_len }}b</span>
        </div>
        <div v-if="ctxStatus.messages.length === 0" class="context-empty">
          暂无上下文数据
        </div>
      </div>
    </div>

    <!-- 边缘折叠/展开箭头 -->
    <div
      class="context-toggle"
      :title="isCollapsed ? '展开上下文' : '折叠上下文'"
      @click="toggle"
    >
      <span>{{ isCollapsed ? '◀' : '▶' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import api from '@/api/agent'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const isCollapsed = ref(true)
const panelWidth = ref(280)
const expandedMsgs = ref(new Set<number>())

const ctxStatus = ref<{
  step: number; policy: any; messages: any[];
  summary_count: number; total_count: number;
}>({ step: 0, policy: null, messages: [], summary_count: 0, total_count: 0 })

function stageIcon(stage: string): string {
  const icons: Record<string, string> = {
    locked: '\u{1F512}', full: '\u{1F4C4}',
    truncated: '\u{2702}\u{FE0F}', oneline: '\u{1F4DD}',
    forgotten: '\u{274C}', summary: '\u{2705}',
  }
  return icons[stage] || '\u{2753}'
}

async function fetchContextStatus() {
  try {
    const resp = await api.get('/agent/context')
    ctxStatus.value = resp.data
  } catch { /* ignore */ }
}

function toggle() {
  isCollapsed.value = !isCollapsed.value
  if (!isCollapsed.value) fetchContextStatus()
}

function toggleMsg(idx: number) {
  if (expandedMsgs.value.has(idx)) {
    expandedMsgs.value.delete(idx)
  } else {
    expandedMsgs.value.add(idx)
  }
}

async function clearContext() {
  try {
    await api.delete('/agent/history')
  } catch { /* ignore */ }
  ctxStatus.value = { step: 0, policy: null, messages: [], summary_count: 0, total_count: 0 }
  expandedMsgs.value.clear()
}

// --- 拖拽调整宽度 ---
let dragging = false
let dragStartX = 0
let dragStartWidth = 0

function onResizeStart(e: MouseEvent) {
  dragging = true
  dragStartX = e.clientX
  dragStartWidth = panelWidth.value
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onResizeMove(e: MouseEvent) {
  if (!dragging) return
  // 向左拖拽 = 增大宽度（鼠标在面板左侧）
  const delta = dragStartX - e.clientX
  const newWidth = Math.max(200, Math.min(500, dragStartWidth + delta))
  panelWidth.value = newWidth
}

function onResizeEnd() {
  dragging = false
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})

// 切换会话时：立即清空旧数据，面板展开则自动刷新
watch(() => chatStore.currentSessionId, () => {
  expandedMsgs.value.clear()
  ctxStatus.value = { step: 0, policy: null, messages: [], summary_count: 0, total_count: 0 }
  if (!isCollapsed.value) {
    fetchContextStatus()
  }
})

// 暴露给父组件
defineExpose({ fetchContextStatus, isCollapsed })
</script>

<style scoped>
.context-panel-wrapper {
  position: relative;
  flex-shrink: 0;
  width: 280px;
  transition: width 0.2s ease;
}

.context-panel-wrapper.collapsed {
  width: 0 !important;
}

.context-panel {
  width: 100%;
  height: 100%;
  background: #1a1b23;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid #2d2e3a;
}

/* 拖拽调整条 */
.resize-handle {
  position: absolute;
  top: 0;
  left: -3px;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 20;
  transition: background 0.15s;
}

.resize-handle:hover {
  background: rgba(64, 158, 255, 0.3);
}

.context-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #2d2e3a;
}

.context-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
}

.clear-btn {
  padding: 3px 10px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 4px;
  color: #f08080;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}

.clear-btn:hover {
  background: rgba(239, 68, 68, 0.25);
}

.context-panel-stats {
  padding: 6px 12px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  display: flex;
  align-items: center;
  gap: 6px;
}

.ctx-summary-badge {
  padding: 1px 6px;
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
  border-radius: 3px;
  font-size: 10px;
}

.context-panel-policy {
  padding: 6px 12px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.35);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

/* 上下文列表 - 自定义滚动条 */
.context-panel-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.context-panel-list::-webkit-scrollbar {
  width: 4px;
}

.context-panel-list::-webkit-scrollbar-track {
  background: transparent;
}

.context-panel-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.context-panel-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* 上下文消息条目 */
.context-msg {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: background 0.15s;
}

.context-msg:hover {
  background: rgba(255, 255, 255, 0.06);
}

/* 默认：单行截断 */
.context-msg .ctx-preview {
  color: rgba(255, 255, 255, 0.55);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  min-width: 0;
}

.context-msg .ctx-sender {
  color: rgba(255, 255, 255, 0.7);
  flex-shrink: 0;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

/* 展开态：多行显示 */
.context-msg.expanded {
  flex-wrap: wrap;
}

.context-msg.expanded .ctx-preview {
  white-space: normal;
  word-break: break-all;
  flex-basis: 100%;
  order: 10;
  margin-top: 2px;
  padding-top: 2px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.context-msg.expanded .ctx-sender {
  max-width: none;
}

.ctx-stage-icon {
  width: 18px;
  text-align: center;
  flex-shrink: 0;
  font-size: 11px;
  padding-top: 1px;
}

.ctx-role {
  padding: 0 4px;
  border-radius: 2px;
  font-size: 9px;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.6);
  flex-shrink: 0;
  min-width: 28px;
  text-align: center;
}

.ctx-age {
  color: rgba(255, 255, 255, 0.35);
  font-size: 9px;
  flex-shrink: 0;
}

.ctx-len {
  color: rgba(255, 255, 255, 0.3);
  font-size: 9px;
  flex-shrink: 0;
}

/* 衰减阶段着色 */
.ctx-stage-locked { border-left: 2px solid #e6a23c; }
.ctx-stage-summary { border-left: 2px solid #67c23a; }
.ctx-stage-full { border-left: 2px solid rgba(255, 255, 255, 0.2); }
.ctx-stage-truncated { border-left: 2px solid #e6a23c; }
.ctx-stage-oneline { border-left: 2px solid #f56c6c; }
.ctx-stage-forgotten { opacity: 0.3; border-left: 2px solid rgba(255, 255, 255, 0.05); }

.context-empty {
  text-align: center;
  color: #666;
  font-size: 12px;
  padding: 20px 0;
}

/* 边缘折叠/展开箭头 */
.context-toggle {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #8b8d9a;
  font-size: 14px;
  background: #1a1b23;
  border: 1px solid #2d2e3a;
  border-right: none;
  border-radius: 6px 0 0 6px;
  z-index: 10;
  transition: color 0.15s, left 0.2s ease;
  left: -28px;
}

.context-toggle:hover {
  color: #fff;
}

/* 折叠态：箭头移到右边缘 */
.context-panel-wrapper.collapsed .context-toggle {
  left: -28px;
  border-left: none;
  border-right: 1px solid #2d2e3a;
  border-radius: 0 6px 6px 0;
}
</style>
