import { reactive } from 'vue'
import type { Message } from '@/types'

function pushMessage(msg: Message) {
  store.messages.push(msg)
}

function setPending(data: { content: string; requestId: string; thought?: string; command?: string }) {
  store.pendingCommand = data.content
  store.pendingRequestId = data.requestId
  store.pendingThought = data.thought || ''
  store.pendingCommandText = data.command || ''
}

function clearPending() {
  store.pendingCommand = ''
  store.pendingRequestId = ''
  store.pendingThought = ''
  store.pendingCommandText = ''
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
  pushMessage,
  setPending,
  clearPending,
  clearMessages
})

export function useChatStore() {
  return store
}
