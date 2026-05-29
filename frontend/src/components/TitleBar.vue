<template>
  <div class="title-bar" @dblclick="handleMaximize">
    <!-- 左侧：应用图标 + 标题 -->
    <div class="title-bar-left">
      <div class="app-icon">🛡</div>
      <span class="app-title">Safe-CLI-Agent</span>
    </div>

    <!-- 中间：页面自定义内容（slot） -->
    <div class="title-bar-center">
      <slot></slot>
    </div>

    <!-- 右侧：自定义操作 + 窗口控制按钮 -->
    <div class="title-bar-right-area">
      <slot name="right"></slot>
    </div>

    <!-- 右侧：窗口控制按钮 -->
    <div class="title-bar-right">
      <button class="title-btn minimize" @click="handleMinimize" title="最小化">
        <svg width="12" height="12" viewBox="0 0 12 12"><rect y="5" width="12" height="1.5" rx="0.75" fill="currentColor"/></svg>
      </button>
      <button class="title-btn maximize" @click="handleMaximize" :title="isMaximized ? '还原' : '最大化'">
        <svg v-if="!isMaximized" width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
        <svg v-else width="12" height="12" viewBox="0 0 12 12"><rect x="2.5" y="0" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/><rect x="0" y="2.5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="currentColor" fill-opacity="0.15"/></svg>
      </button>
      <button class="title-btn close" @click="handleClose" title="关闭">
        <svg width="12" height="12" viewBox="0 0 12 12"><path d="M2 2L10 10M10 2L2 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const isMaximized = ref(false)

onMounted(async () => {
  if (window.electronAPI) {
    isMaximized.value = await window.electronAPI.windowIsMaximized()
  }
})

function handleMinimize() {
  window.electronAPI?.windowMinimize()
}

async function handleMaximize() {
  window.electronAPI?.windowMaximize()
  if (window.electronAPI) {
    isMaximized.value = await window.electronAPI.windowIsMaximized()
  }
}

function handleClose() {
  window.electronAPI?.windowClose()
}
</script>

<style scoped>
.title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 40px;
  background: #0d0e12;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  user-select: none;
  -webkit-app-region: drag;
  flex-shrink: 0;
}

.title-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 14px;
  min-width: 180px;
}

.app-icon {
  font-size: 16px;
}

.app-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  letter-spacing: 0.3px;
}

.title-bar-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  -webkit-app-region: no-drag;
}

.title-bar-right-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 8px;
  -webkit-app-region: no-drag;
}

.title-bar-right {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.title-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 100%;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.45);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.title-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.9);
}

.title-btn.close:hover {
  background: #e81123;
  color: #fff;
}
</style>
