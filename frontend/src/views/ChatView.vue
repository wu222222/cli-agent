<template>
  <div class="chat-container">
    <div class="chat-header">
      <h1>Safe-CLI-Agent</h1>
      <div class="header-actions">
        <button class="header-btn" @click="$router.push('/setup')" title="Docker 配置">Docker</button>
        <span class="status-indicator" :class="{ online: isConnected }">
          {{ isConnected ? '已连接' : '离线' }}
        </span>
      </div>
    </div>

    <div class="chat-messages" ref="messagesContainer">
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message-item"
        :class="{ 'user-message': message.role === 'user', 'system-message': message.role === 'system' }"
      >
        <div class="message-avatar">
          {{ message.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="message-content">
          <div class="message-header">
            <span>{{ message.role === 'user' ? '用户' : (message.agent || 'Agent') }}</span>
            <span class="message-time">{{ message.timestamp }}</span>
          </div>
          <div class="message-body">
            <pre v-if="message.type === 'code'" class="tool-output">{{ message.content }}</pre>
            <p v-else>{{ message.content }}</p>
          </div>
        </div>
      </div>

      <div v-if="isThinking" class="thinking-indicator">
        <span class="thinking-dots"><span></span><span></span><span></span></span>
        <span>Agent 正在思考...</span>
      </div>
    </div>

    <div class="command-preview" v-if="pendingCommand">
      <div class="command-warning">
        <span class="warning-icon">⚠️</span>
        <span>即将执行以下命令，请确认：</span>
      </div>
      <pre class="command-text">{{ pendingCommand }}</pre>
      <div class="command-actions">
        <button class="btn btn-confirm" @click="confirmCommand">确认执行</button>
        <button class="btn btn-cancel" @click="cancelCommand">取消</button>
      </div>
    </div>

    <div class="chat-input">
      <textarea
        v-model="inputMessage"
        placeholder="输入命令或问题..."
        @keydown.enter.exact.prevent="sendMessage"
        rows="3"
      ></textarea>
      <button class="send-btn" @click="sendMessage" :disabled="!inputMessage.trim() || isThinking">
        发送
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { sendMessage as apiSendMessage, sendCuratorTask, connectStream, checkConnection } from '@/api/agent'
import type { Message } from '@/types'

const messages = ref<Message[]>([
  {
    role: 'system',
    content: '欢迎使用 Safe-CLI-Agent！我可以帮助你执行命令行操作。\n输入 /summary 可以让 CuratorAgent 整理对话历史并总结。',
    timestamp: new Date().toLocaleTimeString(),
    thought: '',
    type: 'text',
    agent: 'System'
  }
])

const inputMessage = ref('')
const isThinking = ref(false)
const isConnected = ref(false)
const pendingCommand = ref('')
const pendingRequestId = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const now = () => new Date().toLocaleTimeString()

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const pushMessage = async (msg: Message) => {
  messages.value.push(msg)
  await scrollToBottom()
}

const listenStream = (requestId: string) => {
  connectStream(requestId, {
    onToolStart: (data) => {
      pushMessage({
        role: 'system',
        content: data.content,
        timestamp: now(),
        thought: '',
        type: 'text',
        agent: data.agent
      })
    },
    onToolResult: (data) => {
      pushMessage({
        role: 'system',
        content: data.content,
        timestamp: now(),
        thought: '',
        type: 'code',
        agent: data.agent
      })
    },
    onConfirm: (data) => {
      pendingCommand.value = data.content
      pendingRequestId.value = requestId
      isThinking.value = false
      pushMessage({
        role: 'system',
        content: data.content,
        timestamp: now(),
        thought: '',
        type: 'text',
        agent: data.agent
      })
    },
    onFinal: (data) => {
      pushMessage({
        role: 'system',
        content: data.content,
        timestamp: now(),
        thought: '',
        type: 'text',
        agent: data.agent
      })
      isThinking.value = false
    },
    onError: (data) => {
      pushMessage({
        role: 'system',
        content: `错误：${data.content}`,
        timestamp: now(),
        thought: '',
        type: 'text'
      })
      isThinking.value = false
    }
  })
}

const CURATOR_COMMANDS = ['/summary', '/curator', '/总结', '/整理']

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isThinking.value) return

  const content = inputMessage.value
  inputMessage.value = ''

  await pushMessage({
    role: 'user',
    content,
    timestamp: now(),
    thought: '',
    type: 'text'
  })

  try {
    isThinking.value = true

    // 检测是否为 Curator 命令
    const trimmed = content.trim()
    const isCuratorCommand = CURATOR_COMMANDS.some(cmd => trimmed.startsWith(cmd))
    const curatorTask = isCuratorCommand
      ? trimmed.replace(/^\/\S+\s*/, '').trim() || '分析之前的对话历史，提取关键信息并整理到知识库中。'
      : ''

    if (isCuratorCommand) {
      const response = await sendCuratorTask(curatorTask)
      listenStream(response.request_id)
    } else {
      const response = await apiSendMessage(content)
      listenStream(response.request_id)
    }
  } catch (error) {
    await pushMessage({
      role: 'system',
      content: `错误：${error instanceof Error ? error.message : '未知错误'}`,
      timestamp: now(),
      thought: '',
      type: 'text'
    })
    isThinking.value = false
  }
}

const confirmCommand = async () => {
  if (!pendingCommand.value) return

  const cmd = pendingCommand.value
  pendingCommand.value = ''

  try {
    isThinking.value = true
    const response = await apiSendMessage(cmd, true)
    listenStream(response.request_id)
  } catch (error) {
    await pushMessage({
      role: 'system',
      content: `错误：${error instanceof Error ? error.message : '未知错误'}`,
      timestamp: now(),
      thought: '',
      type: 'text'
    })
    isThinking.value = false
  }
}

const cancelCommand = () => {
  pendingCommand.value = ''
  pendingRequestId.value = ''
}

onMounted(async () => {
  try {
    isConnected.value = await checkConnection()
  } catch {
    isConnected.value = false
  }
})
</script>

<style lang="scss">
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  h1 { color: #fff; font-size: 20px; font-weight: 600; margin: 0; }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .header-btn {
    padding: 4px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.7);
    transition: all 0.2s;
    &:hover { border-color: #007bff; color: #fff; }
  }

  .status-indicator {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    background: #dc3545;
    color: #fff;
    &.online { background: #28a745; }
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.05); }
  &::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 3px; }
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  max-width: 85%;

  &.user-message {
    margin-left: auto;
    flex-direction: row-reverse;
    .message-content { background: #007bff; }
  }

  &.system-message .message-content { background: rgba(255, 255, 255, 0.1); }

  .message-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
  }

  .message-content {
    flex: 1;
    border-radius: 12px;
    padding: 10px 14px;
    color: #fff;

    .message-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
      font-size: 11px;
      opacity: 0.6;
    }

    .message-body {
      font-size: 14px;
      line-height: 1.6;
      p { margin: 0; }
    }
  }
}

.tool-output {
  background: rgba(0, 0, 0, 0.3);
  padding: 8px 10px;
  border-radius: 6px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  margin: 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.command-preview {
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: 12px;
  padding: 16px;
  margin: 0 24px 16px;

  .command-warning {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #ffc107;
    font-size: 14px;
    margin-bottom: 12px;
  }

  .command-text {
    background: rgba(0, 0, 0, 0.3);
    padding: 12px;
    border-radius: 8px;
    color: #fff;
    font-family: 'Fira Code', monospace;
    font-size: 13px;
    margin: 0 0 12px;
    overflow-x: auto;
  }

  .command-actions {
    display: flex;
    gap: 12px;

    .btn {
      padding: 8px 24px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      border: none;
      transition: all 0.2s;

      &.btn-confirm { background: #28a745; color: #fff; &:hover { background: #218838; } }
      &.btn-cancel { background: rgba(255, 255, 255, 0.1); color: #fff; &:hover { background: rgba(255, 255, 255, 0.2); } }
    }
  }
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  color: #fff;
  font-size: 14px;
  align-self: flex-start;

  .thinking-dots {
    display: flex;
    gap: 4px;
    span {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #007bff;
      animation: dotPulse 1.4s infinite ease-in-out;
      &:nth-child(2) { animation-delay: 0.2s; }
      &:nth-child(3) { animation-delay: 0.4s; }
    }
  }
}

@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-top: 1px solid rgba(255, 255, 255, 0.1);

  textarea {
    flex: 1;
    padding: 12px 16px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.05);
    color: #fff;
    font-size: 14px;
    resize: none;
    outline: none;
    &:focus { border-color: #007bff; }
    &::placeholder { color: rgba(255, 255, 255, 0.5); }
  }

  .send-btn {
    padding: 12px 32px;
    background: #007bff;
    color: #fff;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    align-self: flex-end;
    &:hover:not(:disabled) { background: #0069d9; }
    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }
}
</style>
