<template>
  <div class="context-tab">
    <div class="ctx-stats">
      Step {{ ctxStatus.step }} | ~{{ ctxStatus.total_count * 200 }} tok | {{ ctxStatus.total_count }} 条
      <span v-if="ctxStatus.summary_count" class="ctx-summary-badge">{{ ctxStatus.summary_count }} 摘要</span>
      <button class="clear-btn" @click="clearContext" title="清空上下文">清空</button>
    </div>
    <div class="ctx-policy">
      衰减: 完整{{ ctxStatus.policy?.tool_full_turns }} / 截断{{ ctxStatus.policy?.tool_truncate_turns }} / 遗忘{{ ctxStatus.policy?.tool_max_turns }}
    </div>
    <div class="ctx-list">
      <div
        v-for="(msg, idx) in ctxStatus.messages"
        :key="idx"
        class="ctx-msg"
        :class="[`ctx-stage-${msg.stage}`, { expanded: expandedMsgs.has(idx) }]"
        @click="toggleMsg(idx)"
      >
        <span class="ctx-icon">{{ stageIcon(msg.stage) }}</span>
        <span class="ctx-role">{{ msg.role }}</span>
        <span class="ctx-sender">{{ msg.tool_name || msg.sender }}</span>
        <span class="ctx-age">age:{{ msg.age }}</span>
        <span class="ctx-preview">{{ msg.preview }}</span>
        <span class="ctx-len">{{ msg.content_len }}b</span>
      </div>
      <div v-if="ctxStatus.messages.length === 0" class="ctx-empty">暂无上下文数据</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import api from '@/api/agent'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
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

async function fetchContext() {
  try {
    const resp = await api.get('/agent/context')
    ctxStatus.value = resp.data
  } catch { /* ignore */ }
}

function toggleMsg(idx: number) {
  if (expandedMsgs.value.has(idx)) expandedMsgs.value.delete(idx)
  else expandedMsgs.value.add(idx)
}

async function clearContext() {
  try { await api.delete('/agent/history') } catch { /* ignore */ }
  ctxStatus.value = { step: 0, policy: null, messages: [], summary_count: 0, total_count: 0 }
  expandedMsgs.value.clear()
}

// 组件挂载时加载一次上下文
onMounted(() => {
  fetchContext()
})

// 切换会话时清空 + 重新加载
watch(() => chatStore.currentSessionId, () => {
  expandedMsgs.value.clear()
  ctxStatus.value = { step: 0, policy: null, messages: [], summary_count: 0, total_count: 0 }
  fetchContext()
})

// 对话过程中自动刷新上下文（防抖 2s）
let ctxDebounce: ReturnType<typeof setTimeout> | null = null
watch(() => chatStore.messages.length, () => {
  if (ctxDebounce) clearTimeout(ctxDebounce)
  ctxDebounce = setTimeout(() => fetchContext(), 2000)
})

defineExpose({ fetchContext })
</script>

<style scoped>
.context-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.ctx-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.ctx-summary-badge {
  padding: 1px 6px;
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
  border-radius: 3px;
  font-size: 10px;
}

.clear-btn {
  margin-left: auto;
  padding: 2px 8px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 4px;
  color: #f08080;
  font-size: 10px;
  cursor: pointer;
}

.clear-btn:hover { background: rgba(239, 68, 68, 0.25); }

.ctx-policy {
  padding: 4px 10px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.ctx-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ctx-list::-webkit-scrollbar { width: 4px; }
.ctx-list::-webkit-scrollbar-track { background: transparent; }
.ctx-list::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 2px; }

.ctx-msg {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  padding: 3px 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: background 0.15s;
}

.ctx-msg:hover { background: rgba(255, 255, 255, 0.06); }

.ctx-msg .ctx-preview {
  color: rgba(255, 255, 255, 0.55);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  min-width: 0;
}

.ctx-msg .ctx-sender {
  color: rgba(255, 255, 255, 0.7);
  flex-shrink: 0;
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.ctx-msg.expanded { flex-wrap: wrap; }
.ctx-msg.expanded .ctx-preview {
  white-space: normal; word-break: break-all;
  flex-basis: 100%; order: 10; margin-top: 2px; padding-top: 2px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}
.ctx-msg.expanded .ctx-sender { max-width: none; }

.ctx-icon { width: 16px; text-align: center; flex-shrink: 0; font-size: 10px; padding-top: 1px; }
.ctx-role { padding: 0 3px; border-radius: 2px; font-size: 9px; background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.6); flex-shrink: 0; min-width: 24px; text-align: center; }
.ctx-age { color: rgba(255, 255, 255, 0.35); font-size: 9px; flex-shrink: 0; }
.ctx-len { color: rgba(255, 255, 255, 0.3); font-size: 9px; flex-shrink: 0; }

.ctx-stage-locked { border-left: 2px solid #e6a23c; }
.ctx-stage-summary { border-left: 2px solid #67c23a; }
.ctx-stage-full { border-left: 2px solid rgba(255, 255, 255, 0.2); }
.ctx-stage-truncated { border-left: 2px solid #e6a23c; }
.ctx-stage-oneline { border-left: 2px solid #f56c6c; }
.ctx-stage-forgotten { opacity: 0.3; border-left: 2px solid rgba(255, 255, 255, 0.05); }

.ctx-empty { text-align: center; color: #666; font-size: 12px; padding: 20px 0; }
</style>
