<template>
  <div class="chat-container">
    <header class="chat-header">
      <h1>Safe-CLI-Agent</h1>
      <div class="header-actions">
        <el-button size="small" @click="$router.push('/tools')">
          工具设置
        </el-button>
        <div class="status-indicator" :class="{ connected: chatStore.isConnected }"></div>
      </div>
    </header>

    <div class="chat-body">
      <div class="chat-main">
        <div class="chat-messages" ref="messagesContainer">
          <MessageBubble
            v-for="(msg, index) in chatStore.messages"
            :key="index"
            :message="msg"
          />
          <div v-if="chatStore.isThinking" class="thinking-indicator">
            <div class="dot-pulse"></div>
            <span>Agent 正在思考...</span>
          </div>
        </div>

        <ConfirmDialog
          :visible="!!chatStore.pendingCommand"
          :command="chatStore.pendingCommandText || chatStore.pendingCommand"
          :thought="chatStore.pendingThought"
          @confirm="handleConfirm"
          @cancel="handleCancel"
        />

        <div class="chat-input">
          <div class="input-wrapper">
            <textarea
              v-model="inputMessage"
              placeholder="输入命令或问题... (/summary 进行总结)"
              @keydown.enter.exact.prevent="handleSend"
              :disabled="chatStore.isThinking"
              rows="1"
              ref="textareaRef"
            ></textarea>
            <button
              class="send-button"
              @click="handleSend"
              :disabled="!inputMessage.trim() || chatStore.isThinking"
            >
              发送
            </button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { sendMessage, sendCuratorTask, checkConnection } from '@/api/agent'
import api from '@/api/agent'
import { useChatStore } from '@/stores/chat'
import { useSSE } from '@/composables/useSSE'
import MessageBubble from '@/components/MessageBubble.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const router = useRouter()
const chatStore = useChatStore()
const { connect } = useSSE()

// 防止 handleConfirm 清除 pending 时触发 handleCancel
let isConfirming = false

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const CURATOR_COMMANDS = ['/summary', '/curator', '/总结', '/整理']

function isCuratorCommand(text: string): boolean {
  return CURATOR_COMMANDS.some(cmd => text.trim().toLowerCase().startsWith(cmd))
}

function extractCuratorTask(text: string): string {
  const cmd = CURATOR_COMMANDS.find(c => text.trim().toLowerCase().startsWith(c))
  if (!cmd) return text
  return text.slice(cmd.length).trim() || '请总结对话历史'
}

async function handleSend() {
  const msg = inputMessage.value.trim()
  if (!msg || chatStore.isThinking) return

  inputMessage.value = ''

  chatStore.pushMessage({
    role: 'user',
    content: msg,
    timestamp: new Date().toLocaleTimeString(),
    thought: '',
    type: 'text',
  })

  chatStore.isThinking = true

  try {
    let response
    if (isCuratorCommand(msg)) {
      response = await sendCuratorTask(extractCuratorTask(msg))
    } else {
      response = await sendMessage(msg)
    }

    if (response.request_id) {
      connect(response.request_id)
    } else {
      chatStore.pushMessage({
        role: 'system',
        content: response.content,
        timestamp: new Date().toLocaleTimeString(),
        thought: response.thought || '',
        type: 'text',
        agent: response.agent,
      })
      chatStore.isThinking = false
    }
  } catch (error) {
    chatStore.pushMessage({
      role: 'system',
      content: `请求失败: ${error instanceof Error ? error.message : '未知错误'}`,
      timestamp: new Date().toLocaleTimeString(),
      thought: '',
      type: 'text',
      agent: 'System',
    })
    chatStore.isThinking = false
  }
}

async function handleConfirm() {
  isConfirming = true
  const command = chatStore.pendingCommand
  chatStore.clearPending()
  isConfirming = false

  chatStore.isThinking = true

  try {
    const response = await sendMessage(command, true)
    if (response.request_id) {
      connect(response.request_id)
    } else {
      chatStore.pushMessage({
        role: 'system',
        content: response.content,
        timestamp: new Date().toLocaleTimeString(),
        thought: response.thought || '',
        type: 'text',
        agent: response.agent,
      })
      chatStore.isThinking = false
    }
  } catch (error) {
    chatStore.pushMessage({
      role: 'system',
      content: `确认执行失败: ${error instanceof Error ? error.message : '未知错误'}`,
      timestamp: new Date().toLocaleTimeString(),
      thought: '',
      type: 'text',
      agent: 'System',
    })
    chatStore.isThinking = false
  }
}

function handleCancel() {
  // 防止 handleConfirm 的 clearPending 间接触发
  if (isConfirming) return

  chatStore.clearPending()
  chatStore.isThinking = false

  // 通知后端拒绝命令
  api.post('/agent/chat/reject').catch(() => {})

  chatStore.pushMessage({
    role: 'system',
    content: '命令执行已被用户拒绝',
    timestamp: new Date().toLocaleTimeString(),
    thought: '',
    type: 'text',
    agent: 'System',
  })
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, scrollToBottom)
watch(() => chatStore.isThinking, scrollToBottom)

onMounted(async () => {
  try {
    await checkConnection()
    chatStore.isConnected = true
  } catch {
    chatStore.isConnected = false
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: rgba(255, 255, 255, 0.9);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.chat-header h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f56c6c;
  transition: background 0.3s;
}

.status-indicator.connected {
  background: #67c23a;
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.5);
}

.chat-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 15px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  align-self: flex-start;
}

.dot-pulse {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.5; }
}

.chat-input {
  padding: 15px 20px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.input-wrapper {
  display: flex;
  gap: 10px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.input-wrapper:focus-within {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.input-wrapper textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: inherit;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  min-height: 24px;
  max-height: 150px;
  padding: 4px 0;
  outline: none;
}

.input-wrapper textarea::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.send-button {
  padding: 6px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
  align-self: flex-end;
}

.send-button:hover:not(:disabled) {
  background: #66b1ff;
}

.send-button:disabled {
  background: rgba(64, 158, 255, 0.5);
  cursor: not-allowed;
}

</style>
