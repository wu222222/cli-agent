import { reactive } from 'vue'
import type { Message, SessionInfo } from '@/types'

// 恢复会话时的加载标志（跳过自动保存）
let isLoadingSession = false

async function pushMessage(msg: Message) {
  store.messages.push(msg)
  // 恢复会话时不保存（消息已存在于 session 文件中）
  if (isLoadingSession) return
  // 自动保存到当前 session
  if (store.currentSessionId) {
    try {
      const { saveSessionMessage } = await import('@/api/config')
      await saveSessionMessage(store.currentSessionId, {
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
        type: msg.type,
        agent: msg.agent,
        toolName: msg.toolName,
        command: msg.command,
        thought: msg.thought,
      })
    } catch (e) {
      console.error('自动保存消息失败:', e)
    }
  }
}

// 暴露加载标志控制方法
export function setLoadingSession(value: boolean) {
  isLoadingSession = value
}

function setPending(data: { content: string; requestId: string; thought?: string; command?: string; toolName?: string }) {
  store.pendingCommand = data.content
  store.pendingRequestId = data.requestId
  store.pendingThought = data.thought || ''
  store.pendingCommandText = data.command || ''
  store.pendingToolName = data.toolName || ''
}

function clearPending() {
  store.pendingCommand = ''
  store.pendingRequestId = ''
  store.pendingThought = ''
  store.pendingCommandText = ''
  store.pendingToolName = ''
}

function clearMessages() {
  store.messages = []
  store.isThinking = false
}

const store = reactive({
  messages: [] as Message[],
  isThinking: false,
  isConnected: false,
  currentTool: '',  // 当前正在执行的工具名（thinking 时显示）
  pendingCommand: '',
  pendingRequestId: '',
  pendingThought: '',
  pendingCommandText: '',
  pendingToolName: '',
  // === Session 管理 ===
  currentSessionId: null as string | null,
  sessions: [] as SessionInfo[],
  toolsUpdatedAt: 0,  // 工具配置更新时间戳，用于触发 HistoryPanel 刷新
  pushMessage,
  setPending,
  clearPending,
  clearMessages
})

export function useChatStore() {
  return store
}
