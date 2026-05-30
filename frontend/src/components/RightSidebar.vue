<template>
  <div class="right-sidebar" :class="{ expanded: !!activeTab }">
    <!-- 内容面板（始终渲染，通过 display 控制显隐，保留组件状态） -->
    <div v-show="activeTab" class="sidebar-content" :style="{ width: panelWidth + 'px' }">
      <!-- 拖拽调整条 -->
      <div class="resize-handle" @mousedown="onResizeStart"></div>

      <!-- 上下文 tab -->
      <div v-show="activeTab === 'context'" class="tab-pane">
        <ContextTab ref="contextTabRef" />
      </div>
      <!-- 工具 tab -->
      <div v-show="activeTab === 'tools'" class="tab-pane">
        <ToolsTab @navigate="activeTab = null" />
      </div>
    </div>

    <!-- 图标栏（始终在最右侧） -->
    <div class="sidebar-icons">
      <div
        class="icon-btn"
        :class="{ active: activeTab === 'context' }"
        @click="toggleTab('context')"
        title="上下文"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </div>
      <div
        class="icon-btn"
        :class="{ active: activeTab === 'tools' }"
        @click="toggleTab('tools')"
        title="工具"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
        </svg>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import ContextTab from './ContextTab.vue'
import ToolsTab from './ToolsTab.vue'

const chatStore = useChatStore()
const activeTab = ref<string | null>(null)
const contextTabRef = ref<InstanceType<typeof ContextTab> | null>(null)
const panelWidth = ref(280)

function toggleTab(tab: string) {
  activeTab.value = activeTab.value === tab ? null : tab
  // 打开上下文 tab 时刷新数据
  if (activeTab.value === 'context') {
    contextTabRef.value?.fetchContext()
  }
}

// 切换会话时重置 tab（上下文数据由 ContextTab 自己处理）
watch(() => chatStore.currentSessionId, () => {
  // 不自动切换 tab，但 ContextTab 内部会清空并刷新数据
})

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
  const delta = dragStartX - e.clientX
  panelWidth.value = Math.max(200, Math.min(450, dragStartWidth + delta))
}

function onResizeEnd() {
  dragging = false
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// 暴露给父组件
defineExpose({ activeTab })
</script>

<style scoped>
.right-sidebar {
  display: flex;
  flex-shrink: 0;
  height: 100%;
}

/* tab 内容区 */
.tab-pane {
  height: 100%;
  overflow: hidden;
}

/* 内容面板 */
.sidebar-content {
  position: relative;
  height: 100%;
  background: #1a1b23;
  border-left: 1px solid #2d2e3a;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease;
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

/* 面板显隐过渡 */
.sidebar-content {
  transition: width 0.2s ease;
}

/* 图标栏 */
.sidebar-icons {
  display: flex;
  flex-direction: column;
  width: 40px;
  height: 100%;
  background: #0d0e12;
  border-left: 1px solid #2d2e3a;
  padding-top: 8px;
  gap: 4px;
  flex-shrink: 0;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 36px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.35);
  transition: color 0.15s, background 0.15s;
  border-radius: 0;
}

.icon-btn:hover {
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.05);
}

.icon-btn.active {
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
  border-left: 2px solid #409eff;
}
</style>
