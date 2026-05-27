<template>
  <div class="title-bar" @dblclick="handleMaximize">
    <!-- 左侧：应用图标 + 标题 -->
    <div class="title-bar-left">
      <div class="app-icon">🛡</div>
      <span class="app-title">Safe-CLI-Agent</span>
    </div>

    <!-- 右侧：窗口控制按钮 -->
    <div class="title-bar-right">
      <button class="title-btn minimize" @click="handleMinimize" title="最小化">
        <span>─</span>
      </button>
      <button class="title-btn maximize" @click="handleMaximize" :title="isMaximized ? '还原' : '最大化'">
        <span v-if="isMaximized">❐</span>
        <span v-else>□</span>
      </button>
      <button class="title-btn close" @click="handleClose" title="关闭">
        <span>✕</span>
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
  height: 32px;
  background: #0f1015;
  border-bottom: 1px solid #1a1b23;
  user-select: none;
  -webkit-app-region: drag;  /* 允许拖动窗口 */
}

.title-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 12px;
}

.app-icon {
  font-size: 16px;
}

.app-title {
  font-size: 13px;
  font-weight: 500;
  color: #e0e0e0;
}

.title-bar-right {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;  /* 按钮不可拖动 */
}

.title-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 100%;
  background: none;
  border: none;
  color: #8b8d9a;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.title-btn:hover {
  background: #2d2e3a;
  color: #e0e0e0;
}

.title-btn.close:hover {
  background: #e81123;
  color: #fff;
}
</style>
