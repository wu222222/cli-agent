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
          <span v-if="message.command" class="tool-result-cmd">$ {{ message.command }}</span>
        </div>
        <pre class="tool-result-output">{{ message.content }}</pre>
      </div>
      <ToolCard v-else-if="message.type === 'tool_card' && message.toolState" :tool-state="message.toolState" />
      <pre v-else-if="message.type === 'code'" class="tool-output">{{ message.content }}</pre>
      <p v-else>{{ message.content }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Message } from '@/types'
import ToolCard from './ToolCard.vue'

defineProps<{
  message: Message
}>()
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
