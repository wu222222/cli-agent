<template>
  <div class="chat-container">
    <!-- 统一标题栏 -->
    <TitleBar>
      <template #right>
        <div class="status-indicator" :class="{ connected: chatStore.isConnected }"></div>
      </template>
    </TitleBar>

    <div class="chat-body">
      <!-- 左侧历史对话面板 -->
      <HistoryPanel
        ref="historyPanelRef"
        @new-chat="handleNewChat"
        @resume-session="handleResumeSession"
      />

      <div class="chat-main">
        <div class="chat-messages" ref="messagesContainer">
          <MessageBubble
            v-for="(msg, index) in chatStore.messages"
            :key="index"
            :message="msg"
          />
          <div v-if="chatStore.isThinking" class="thinking-indicator">
            <div class="dot-pulse"></div>
            <span v-if="chatStore.currentTool">正在执行: {{ chatStore.currentTool }}...</span>
            <span v-else>Agent 正在思考...</span>
          </div>
        </div>

        <!-- 内嵌确认面板（替代模态弹窗） -->
        <InlineConfirm
          :visible="!!chatStore.pendingCommand"
          :command="chatStore.pendingCommandText || chatStore.pendingCommand"
          :thought="chatStore.pendingThought"
          :tool-name="chatStore.pendingToolName"
          @confirm="handleConfirm"
          @cancel="handleCancel"
        />

        <div class="chat-input">
          <div class="command-hints" v-if="showHints">
            <div
              v-for="(hint, idx) in filteredHints"
              :key="hint.trigger"
              class="hint-item"
              :class="{ active: idx === selectedHint }"
              @mousedown.prevent="selectHint(hint)"
            >
              <span class="hint-trigger">{{ hint.trigger }}</span>
              <span class="hint-desc">{{ hint.description }}</span>
              <span v-if="hint.isPlugin" class="hint-tag">插件</span>
            </div>
          </div>
          <div class="input-wrapper">
            <textarea
              v-model="inputMessage"
              :placeholder="chatStore.currentSessionId ? '输入命令或问题... (输入 / 查看可用命令)' : '请先新建或选择一个对话'"
              @keydown.enter.exact.prevent="handleSend"
              @keydown="handleHintKeydown"
              :disabled="chatStore.isThinking"
              rows="1"
              ref="textareaRef"
            ></textarea>
            <button
              v-if="!chatStore.isThinking"
              class="send-button"
              @click="handleSend"
              :disabled="!inputMessage.trim() || !chatStore.currentSessionId"
            >
              发送
            </button>
            <button
              v-else
              class="stop-button"
              @click="stopAgent"
            >
              ⏹ 终止
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧栏 -->
      <RightSidebar ref="rightSidebarRef" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onActivated } from 'vue'
import { sendMessage, sendCuratorTask, checkConnection } from '@/api/agent'
import api from '@/api/agent'
import { executeCommandPlugin } from '@/api/config'
import { useChatStore } from '@/stores/chat'
import { useSSE } from '@/composables/useSSE'
import MessageBubble from '@/components/MessageBubble.vue'
import InlineConfirm from '@/components/InlineConfirm.vue'
import HistoryPanel from '@/components/HistoryPanel.vue'
import RightSidebar from '@/components/RightSidebar.vue'
import TitleBar from '@/components/TitleBar.vue'

const chatStore = useChatStore()
const { connect, disconnect } = useSSE()
const historyPanelRef = ref<InstanceType<typeof HistoryPanel> | null>(null)
const rightSidebarRef = ref<InstanceType<typeof RightSidebar> | null>(null)

// 防止 handleConfirm 清除 pending 时触发 handleCancel
let isConfirming = false

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// --- 命令提示系统 ---
interface CommandHint {
  name: string
  trigger: string
  description: string
  isPlugin: boolean
  agentType: string
}

const commandHints = ref<CommandHint[]>([])
const showHints = ref(false)
const selectedHint = ref(-1)

// 加载命令插件 — command_trigger 完全由 API 提供，不再硬编码
async function loadCommandHints() {
  try {
    const resp = await api.get('/plugins')
    const plugins = resp.data || []
    const hints: CommandHint[] = [
      { name: '/help', trigger: '/help', description: '查看所有可用命令', isPlugin: false, agentType: 'none' },
    ]
    for (const p of plugins) {
      if (p.plugin_type === 'command' && p.status === 'running') {
        const trigger = p.command_trigger || `/${p.name}`
        hints.push({
          name: `/${p.name}`,
          trigger: trigger,
          description: p.description,
          isPlugin: true,
          agentType: p.agent_type || 'none',
        })
      }
    }
    commandHints.value = hints
  } catch {
    commandHints.value = [{ name: '/help', trigger: '/help', description: '查看所有可用命令', isPlugin: false, agentType: 'none' }]
  }
}

// 过滤匹配的命令提示
const filteredHints = computed(() => {
  const q = inputMessage.value.trim().toLowerCase()
  if (!q.startsWith('/')) return []
  return commandHints.value.filter(h =>
    h.trigger.toLowerCase().startsWith(q) || h.name.toLowerCase().startsWith(q)
  )
})

watch(inputMessage, (val) => {
  showHints.value = val.startsWith('/') && filteredHints.value.length > 0
  selectedHint.value = -1
})

function selectHint(hint: CommandHint) {
  inputMessage.value = hint.trigger + ' '
  showHints.value = false
  textareaRef.value?.focus()
}

function handleHintKeydown(e: KeyboardEvent) {
  if (!showHints.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedHint.value = Math.min(selectedHint.value + 1, filteredHints.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedHint.value = Math.max(selectedHint.value - 1, -1)
  } else if (e.key === 'Enter' && selectedHint.value >= 0) {
    e.preventDefault()
    selectHint(filteredHints.value[selectedHint.value])
  } else if (e.key === 'Escape') {
    showHints.value = false
  }
}

function handleHelp(): string {
  const lines = ['可用命令：']
  for (const h of commandHints.value) {
    lines.push(`  ${h.trigger}  — ${h.description}`)
  }
  if (commandHints.value.length <= 1) {
    lines.push('  （当前没有启用的命令插件，请在工具设置页面启用）')
  }
  lines.push('')
  lines.push('输入任意自然语言，Agent 会自动分析并执行。')
  return lines.join('\n')
}

// 检测命令插件触发器 — 完全由 commandHints 驱动，无硬编码
function detectCommandTrigger(text: string): { toolName: string; trigger: string } | null {
  const trimmed = text.trim().toLowerCase()
  for (const h of commandHints.value) {
    if (h.isPlugin && trimmed.startsWith(h.trigger.toLowerCase())) {
      return { toolName: h.name.replace(/^\//, ''), trigger: h.trigger }
    }
  }
  return null
}

function extractCommandArgs(text: string, trigger: string): string {
  return text.trim().slice(trigger.length).trim() || ''
}

async function handleSend() {
  const msg = inputMessage.value.trim()
  if (!msg || chatStore.isThinking) return

  inputMessage.value = ''
  showHints.value = false

  // 自动创建 session（首条消息时）
  await ensureSession()

  const userMsg = {
    role: 'user' as const,
    content: msg,
    timestamp: new Date().toLocaleTimeString(),
    thought: '',
    type: 'text' as const,
  }
  // pushMessage 内部已自动保存到 session，无需重复调用
  chatStore.pushMessage(userMsg)

  // /help 命令直接返回帮助信息
  if (msg.toLowerCase() === '/help') {
    chatStore.pushMessage({
      role: 'system',
      content: handleHelp(),
      timestamp: new Date().toLocaleTimeString(),
      thought: '',
      type: 'text',
      agent: 'System',
    })
    return
  }

  chatStore.isThinking = true

  try {
    let response
    const cmdTrigger = detectCommandTrigger(msg)
    if (cmdTrigger) {
      const args = extractCommandArgs(msg, cmdTrigger.trigger)
      // 根据 agent_type 决定路由（由 API 返回，不再硬编码）
      const hint = commandHints.value.find(h => h.trigger === cmdTrigger.trigger)
      const agentType = hint?.agentType || 'none'

      if (agentType === 'curator') {
        // agent_type=curator → 走 CuratorAgent
        response = await sendCuratorTask(args || '请总结对话历史')
      } else {
        // agent_type=none → 直接在容器中执行
        chatStore.isThinking = false
        const result = await executeCommandPlugin(cmdTrigger.toolName, args || undefined)
        chatStore.pushMessage({
          role: 'system',
          content: result.success
            ? (result.output || '（无输出）')
            : `执行失败: ${result.message || '未知错误'}`,
          timestamp: new Date().toLocaleTimeString(),
          thought: '',
          type: 'tool_result',
          agent: cmdTrigger.toolName,
          toolName: cmdTrigger.toolName,
          command: args || '(默认命令)',
        })
        return
      }
    } else {
      response = await sendMessage(msg, false, chatStore.currentSessionId || undefined)
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

// ============================================================
// Session 管理
// ============================================================

// 新建对话（HistoryPanel 已创建 session 并设置 currentSessionId，这里只清消息）
function handleNewChat() {
  chatStore.clearMessages()
}

// 恢复会话（含插件匹配）
function handleResumeSession(data: { session_id: string; messages: any[]; tool_names: string[] }) {
  chatStore.currentSessionId = data.session_id
  // 插件配置已在 resumeSession API 中恢复
  // 消息已在 HistoryPanel 中恢复
}

// 保存消息到当前 session
// async function saveMessageToSession(msg: any) {
//   if (!chatStore.currentSessionId) return
//   try {
//     await saveSessionMessage(chatStore.currentSessionId, msg)
//   } catch (e) {
//     console.error('保存消息失败:', e)
//   }
// }

// 自动创建 session（首条消息时）
async function ensureSession() {
  if (!chatStore.currentSessionId) {
    try {
      const { createSession } = await import('@/api/config')
      const result = await createSession()
      chatStore.currentSessionId = result.session_id
      historyPanelRef.value?.loadSessions()
    } catch (e) {
      console.error('创建会话失败:', e)
    }
  }
}

async function handleConfirm(guidance: string = '') {
  isConfirming = true
  chatStore.clearPending()
  isConfirming = false

  chatStore.isThinking = true

  try {
    const response = await api.post('/agent/chat/confirm', { message: guidance, session_id: chatStore.currentSessionId })
    if (response.data.request_id) {
      connect(response.data.request_id)
    } else {
      chatStore.pushMessage({
        role: 'system',
        content: response.data.content,
        timestamp: new Date().toLocaleTimeString(),
        thought: response.data.thought || '',
        type: 'text',
        agent: response.data.agent,
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

async function handleCancel(guidance: string = '') {
  // 防止 handleConfirm 的 clearPending 间接触发
  if (isConfirming) return

  chatStore.clearPending()

  if (guidance) {
    // 有引导 → 重新思考，保持 thinking 状态
    chatStore.isThinking = true
    try {
      const response = await api.post('/agent/chat/reject', { message: guidance })
      if (response.data.request_id) {
        connect(response.data.request_id)
        chatStore.pushMessage({
          role: 'system',
          content: `已引导 Agent 重新思考: ${guidance}`,
          timestamp: new Date().toLocaleTimeString(),
          thought: '',
          type: 'text',
          agent: 'System',
        })
        return
      }
    } catch {}
    chatStore.isThinking = false
  } else {
    // 无引导 → 终止
    chatStore.isThinking = false
    api.post('/agent/chat/reject', { message: '' }).catch(() => {})
  }

  chatStore.pushMessage({
    role: 'system',
    content: guidance ? '已将引导信息发送给 Agent，重新思考中...' : '命令执行已被用户拒绝',
    timestamp: new Date().toLocaleTimeString(),
    thought: '',
    type: 'text',
    agent: 'System',
  })
}

function stopAgent() {
  disconnect()
  chatStore.isThinking = false
  chatStore.pushMessage({
    role: 'system', content: '任务已被用户终止',
    timestamp: new Date().toLocaleTimeString(),
    thought: '', type: 'text', agent: 'System',
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
  loadCommandHints()
})

onActivated(() => {
  loadCommandHints()
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
  padding-right: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 自定义滚动条 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
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
  padding: 12px 20px;
  background: transparent;
  position: relative;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.command-hints {
  position: absolute;
  bottom: 100%;
  left: 20px;
  right: 20px;
  background: rgba(30, 30, 50, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 6px 0;
  margin-bottom: 8px;
  max-height: 200px;
  overflow-y: auto;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.3);
}

.hint-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  cursor: pointer;
  transition: background 0.15s;
}

.hint-item:hover,
.hint-item.active {
  background: rgba(64, 158, 255, 0.12);
}

.hint-trigger {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  font-weight: 600;
  color: #79bbff;
  min-width: 80px;
}

.hint-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  flex: 1;
}

.hint-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.input-wrapper {
  display: flex;
  gap: 10px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.input-wrapper:focus-within {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(64, 158, 255, 0.4);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(64, 158, 255, 0.15);
}

.input-wrapper textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  min-height: 24px;
  max-height: 150px;
  padding: 2px 0;
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

.stop-button {
  padding: 8px 18px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.stop-button:hover {
  background: #f78989;
}

</style>
