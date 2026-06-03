<template>
  <div v-if="visible" class="inline-confirm-wrapper">
    <!-- 收缩/展开箭头 -->
    <div class="collapse-toggle" @click="isExpanded = !isExpanded">
      <span class="collapse-arrow" :class="{ collapsed: !isExpanded }">↓</span>
      <span class="collapse-label">{{ isExpanded ? '收起' : '待确认' }}</span>
    </div>

    <!-- 确认面板 -->
    <div v-if="isExpanded" class="inline-confirm-panel">
      <div class="confirm-header">
        <span class="confirm-title">命令执行确认</span>
        <span v-if="toolName" class="confirm-tool-badge">{{ toolName }}</span>
      </div>

      <!-- 思考过程 -->
      <div v-if="thought" class="confirm-thought">
        <div class="thought-label">💭 思考过程</div>
        <div class="thought-text">{{ thought }}</div>
      </div>

      <!-- 即将执行的命令 -->
      <div class="confirm-command-section">
        <div class="command-label">即将执行的命令：</div>
        <pre class="command-block">{{ command }}</pre>
      </div>

      <!-- 引导输入 -->
      <div class="confirm-guidance">
        <textarea
          v-model="guidance"
          class="guidance-input"
          placeholder="可选：输入引导信息调整 Agent 方向..."
          rows="2"
        ></textarea>
      </div>

      <!-- 操作按钮 -->
      <div class="confirm-actions">
        <button class="btn-reject" @click="handleReject">
          {{ guidance ? '拒绝 + 引导' : '拒绝' }}
        </button>
        <button class="btn-accept" @click="handleAccept">
          {{ guidance ? '执行 + 引导' : '执行' }}
        </button>
        <button class="btn-always" @click="handleAlwaysExecute" title="同类命令以后都自动执行">
          ⚡ 一直执行
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  command: string
  thought?: string
  toolName?: string
}>()

const emit = defineEmits<{
  (e: 'confirm', guidance: string): void
  (e: 'cancel', guidance: string): void
  (e: 'always-execute', data: { tool: string; command: string }): void
}>()

const guidance = ref('')
const isExpanded = ref(true)

// 有待确认命令时自动展开
watch(() => props.visible, (val) => {
  if (val) {
    isExpanded.value = true
    guidance.value = ''
  }
})

function handleAccept() {
  emit('confirm', guidance.value)
  guidance.value = ''
}

function handleReject() {
  emit('cancel', guidance.value)
  guidance.value = ''
}

function handleAlwaysExecute() {
  emit('always-execute', {
    tool: props.toolName || '',
    command: props.command,
  })
  // 同时执行本次命令
  emit('confirm', guidance.value)
  guidance.value = ''
}
</script>

<style scoped>
.inline-confirm-wrapper {
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

/* 收缩/展开箭头 */
.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.collapse-toggle:hover {
  background: rgba(255, 255, 255, 0.04);
}

.collapse-arrow {
  font-size: 14px;
  color: #e6a23c;
  transition: transform 0.2s;
}

.collapse-arrow.collapsed {
  transform: rotate(-90deg);
}

.collapse-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

/* 确认面板 */
.inline-confirm-panel {
  padding: 0 20px 16px;
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.confirm-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.confirm-tool-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: rgba(64, 158, 255, 0.15);
  border-radius: 4px;
  color: #79bbff;
  font-family: 'Fira Code', 'Consolas', monospace;
}

/* 思考过程 */
.confirm-thought {
  padding: 12px;
  background: rgba(103, 194, 58, 0.08);
  border-radius: 8px;
  border-left: 3px solid rgba(103, 194, 58, 0.5);
  margin-bottom: 12px;
}

.thought-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 6px;
}

.thought-text {
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.85);
}

/* 命令区域 */
.confirm-command-section {
  margin-bottom: 12px;
}

.command-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 6px;
}

.command-block {
  margin: 0;
  padding: 12px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: #409eff;
  overflow-x: auto;
  overflow-y: auto;
  max-height: 200px;
  white-space: pre-wrap;
  word-break: break-all;
}

.command-block::-webkit-scrollbar { width: 4px; height: 4px; }
.command-block::-webkit-scrollbar-track { background: transparent; }
.command-block::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 2px; }

/* 引导输入 */
.confirm-guidance {
  margin-bottom: 12px;
}

.guidance-input {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}

.guidance-input:focus {
  border-color: rgba(64, 158, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
}

.guidance-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}

/* 操作按钮 */
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-reject,
.btn-accept {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-reject {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
}

.btn-reject:hover {
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.9);
}

.btn-accept {
  background: #2563eb;
  color: #fff;
}

.btn-accept:hover {
  background: #1d4ed8;
}

.btn-always {
  padding: 8px 16px;
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 6px;
  color: #22c55e;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-always:hover {
  background: rgba(34, 197, 94, 0.25);
  border-color: rgba(34, 197, 94, 0.5);
}
</style>
