<template>
  <div class="message" :class="[message.role, message.type, `agent-${message.agent || 'unknown'}`]">
    <div class="message-header">
      <span class="agent-name">{{ message.agent || (message.role === 'user' ? '用户' : '系统') }}</span>
      <span class="timestamp">{{ message.timestamp }}</span>
    </div>
    <div v-if="message.thought" class="thought-process">
      <div class="thought-label">💭 思考过程</div>
      <div class="thought-content">{{ message.thought }}</div>
    </div>
    <div class="message-body">
      <div v-if="message.type === 'thought'" class="thought-bubble">
        <span class="thought-icon">💭</span>
        <span class="thought-text">{{ message.content }}</span>
      </div>
      <div v-else-if="message.type === 'tool_result'" class="tool-result-block">
        <div class="tool-result-header">
          <span class="tool-result-icon">⚙</span>
          <span class="tool-result-name">{{ message.toolName || 'tool' }}</span>
          <span v-if="message.command" class="tool-result-cmd">$ {{ truncateCommand(message.command) }}</span>
        </div>
        <pre class="tool-result-output" :class="{ collapsed: needsCollapse && isCollapsed }">{{ displayContent }}</pre>
        <button
          v-if="needsCollapse"
          class="collapse-toggle"
          @click="isCollapsed = !isCollapsed"
        >
          {{ isCollapsed ? `展开全部 (${lineCount} 行)` : '收起' }}
        </button>
      </div>
      <ToolCard v-else-if="message.type === 'tool_card' && message.toolState" :tool-state="message.toolState" />
      <pre v-else-if="message.type === 'code'" class="tool-output">{{ message.content }}</pre>
      <p v-else>{{ message.content }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Message } from '@/types'
import ToolCard from './ToolCard.vue'

const props = defineProps<{
  message: Message
}>()

// 命令截断
const MAX_CMD_LEN = 120
function truncateCommand(cmd: string): string {
  if (cmd.length <= MAX_CMD_LEN) return cmd
  return cmd.slice(0, MAX_CMD_LEN) + '...'
}

// 长输出折叠
const isCollapsed = ref(true)
const COLLAPSE_LINES = 10
const COLLAPSE_CHARS = 3000

const needsCollapse = computed(() => {
  if (props.message.type !== 'tool_result') return false
  const content = props.message.content || ''
  const lines = content.split('\n').length
  return lines > COLLAPSE_LINES || content.length > COLLAPSE_CHARS
})

const lineCount = computed(() => {
  return (props.message.content || '').split('\n').length
})

const displayContent = computed(() => {
  if (props.message.type !== 'tool_result') return props.message.content
  const content = props.message.content || ''

  // 尝试 JSON 格式化
  const trimmed = content.trim()
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      const parsed = JSON.parse(trimmed)
      return JSON.stringify(parsed, null, 2)
    } catch {
      // 不是有效 JSON，保持原样
    }
  }

  // 折叠：只显示前 COLLAPSE_LINES 行
  if (needsCollapse.value && isCollapsed.value) {
    return content.split('\n').slice(0, COLLAPSE_LINES).join('\n')
  }
  return content
})
</script>

<style scoped>
.message {
  max-width: 80%;
  padding: 10px 15px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin: 5px 0;
}

.message.user {
  margin-left: auto;
  background: rgba(64, 158, 255, 0.2);
  border-color: rgba(64, 158, 255, 0.3);
}

.message.system {
  margin-right: auto;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
}

.agent-name {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.timestamp {
  color: rgba(255, 255, 255, 0.5);
  margin-left: 10px;
}

.thought-process {
  margin: 8px 0;
  padding: 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  border-left: 3px solid rgba(103, 194, 58, 0.5);
}

.thought-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 4px;
}

.thought-content {
  font-size: 13px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.8);
}

.message-body p {
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-output {
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
}

/* Thought 气泡 */
.thought-bubble {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(103, 194, 58, 0.08);
  border-radius: 8px;
  border-left: 3px solid rgba(103, 194, 58, 0.5);
}

.thought-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.thought-text {
  font-size: 13px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.75);
}

/* Tool result 气泡 */
.tool-result-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-result-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.tool-result-icon {
  font-size: 13px;
}

.tool-result-name {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.tool-result-cmd {
  margin-left: 4px;
  padding: 1px 8px;
  background: rgba(64, 158, 255, 0.12);
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  color: #79bbff;
}

.tool-result-output.collapsed {
  max-height: 400px;
  overflow: hidden;
  mask-image: linear-gradient(to bottom, black 60%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, black 60%, transparent 100%);
}

.collapse-toggle {
  display: block;
  margin-top: 4px;
  padding: 4px 12px;
  background: rgba(64, 158, 255, 0.12);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 4px;
  color: #79bbff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.collapse-toggle:hover {
  background: rgba(64, 158, 255, 0.2);
}

.tool-result-output {
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
</style>
