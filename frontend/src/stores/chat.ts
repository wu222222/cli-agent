import { reactive } from 'vue'
import type { Message, SessionInfo } from '@/types'

async function pushMessage(msg: Message) {
  store.messages.push(msg)
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
  store.pendingMinimized = false
}

function clearMessages() {
  store.messages.splice(0)
  store.isThinking = false
}

const store = reactive({
  messages: [] as Message[],
  isThinking: false,
  isConnected: false,
  pendingCommand: '',
  pendingRequestId: '',
  pendingThought: '',
  pendingCommandText: '',
  pendingToolName: '',
  pendingMinimized: false,
  // === Session 管理 ===
  currentSessionId: null as string | null,
  sessions: [] as SessionInfo[],
  pushMessage,
  setPending,
  clearPending,
  clearMessages
})

export function useChatStore() {
  return store
}
