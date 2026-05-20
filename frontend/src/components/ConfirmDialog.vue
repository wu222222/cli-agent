<template>
  <el-dialog
    :model-value="visible"
    title="命令执行确认"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    class="confirm-dialog"
    :append-to-body="true"
    destroy-on-close
  >
    <div class="confirm-content">
      <div v-if="thought" class="confirm-thought">
        <div class="confirm-thought-label">💭 思考过程</div>
        <div class="confirm-thought-text">{{ thought }}</div>
      </div>
      <div v-if="toolName" class="confirm-tool-name">
        执行工具：<code>{{ toolName }}</code>
      </div>
      <div class="confirm-command-section">
        <div class="confirm-command-label">即将执行的命令：</div>
        <pre class="confirm-command">{{ command }}</pre>
      </div>
      <div class="confirm-guidance">
        <textarea
          v-model="guidance"
          class="guidance-input"
          :placeholder="guidancePlaceholder"
          rows="2"
        ></textarea>
      </div>
    </div>
    <template #footer>
      <div class="confirm-actions">
        <el-button @click="$emit('cancel', guidance)">
          {{ guidance ? '拒绝 + 引导' : '拒绝' }}
        </el-button>
        <el-button type="primary" @click="$emit('confirm', guidance)">
          {{ guidance ? '执行 + 引导' : '执行' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  command: string
  thought?: string
  toolName?: string
}>()

const guidance = ref('')

// 对话框关闭时清空引导文本
watch(() => props.visible, (val) => {
  if (!val) guidance.value = ''
})

const guidancePlaceholder = computed(() =>
  guidance.value
    ? '输入引导信息...'
    : '可选：输入引导信息调整 Agent 方向...'
)

defineEmits<{
  confirm: [guidance: string]
  cancel: [guidance: string]
}>()
</script>

<style scoped>
.confirm-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.confirm-thought {
  padding: 12px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: 8px;
  border-left: 3px solid rgba(103, 194, 58, 0.5);
}

.confirm-thought-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8px;
}

.confirm-thought-text {
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.9);
}

.confirm-tool-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.confirm-tool-name code {
  padding: 2px 8px;
  background: rgba(64, 158, 255, 0.15);
  border-radius: 4px;
  color: #79bbff;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

.confirm-command-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.confirm-command-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}

.confirm-command {
  margin: 0;
  padding: 12px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: #409eff;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.confirm-guidance {
  margin-top: 4px;
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

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

<style>
/* 全局样式：el-dialog 渲染在 body 上，scoped 无法覆盖 */
.el-dialog.confirm-dialog {
  background: rgba(30, 30, 50, 0.98) !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 12px !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5) !important;
}

.el-dialog.confirm-dialog .el-dialog__header {
  padding: 20px 20px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.el-dialog.confirm-dialog .el-dialog__title {
  color: rgba(255, 255, 255, 0.9) !important;
  font-weight: 600;
}

.el-dialog.confirm-dialog .el-dialog__body {
  color: rgba(255, 255, 255, 0.85) !important;
  padding: 20px;
}

.el-dialog.confirm-dialog .el-dialog__footer {
  padding: 10px 20px 20px;
}

.el-overlay:has(.confirm-dialog) {
  background-color: rgba(0, 0, 0, 0.6) !important;
}
</style>
