import axios from 'axios'
import type { ApiResponse } from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

export { api }
export default api

export interface ChatApiResponse extends ApiResponse {
  request_id: string
}

export const sendMessage = async (message: string, confirmed: boolean = false): Promise<ChatApiResponse> => {
  const endpoint = confirmed ? '/agent/chat/confirm' : '/agent/chat'
  const response = await api.post(endpoint, { message, confirmed })
  return response.data
}

export const sendCuratorTask = async (task: string): Promise<ChatApiResponse> => {
  const response = await api.post('/agent/curator', { task })
  return response.data
}

export const connectStream = (requestId: string, handlers: {
  onToolStart?: (data: { agent: string; tool: string; tool_type?: string; content: string }) => void
  onToolResult?: (data: { agent: string; tool: string; tool_type?: string; content: string }) => void
  onConfirm?: (data: { content: string; agent: string }) => void
  onFinal?: (data: { content: string; agent: string }) => void
  onError?: (data: { content: string }) => void
  onOpen?: () => void
}): EventSource => {
  const es = new EventSource(`/api/agent/chat/stream?request_id=${requestId}`)

  es.addEventListener('tool_start', (e) => {
    handlers.onToolStart?.(JSON.parse(e.data))
  })
  es.addEventListener('tool_result', (e) => {
    handlers.onToolResult?.(JSON.parse(e.data))
  })
  es.addEventListener('confirm', (e) => {
    handlers.onConfirm?.(JSON.parse(e.data))
  })
  es.addEventListener('final', (e) => {
    handlers.onFinal?.(JSON.parse(e.data))
    es.close()
  })
  es.addEventListener('error', (e: Event) => {
    const msgEvent = e as MessageEvent
    if (msgEvent.data) {
      handlers.onError?.(JSON.parse(msgEvent.data))
    }
    es.close()
  })
  es.onopen = () => handlers.onOpen?.()

  return es
}

export const checkConnection = async (): Promise<boolean> => {
  try {
    await api.get('/health')
    return true
  } catch {
    return false
  }
}

export const getHistory = async (): Promise<unknown[]> => {
  const response = await api.get('/agent/history')
  return response.data
}

export const clearHistory = async (): Promise<void> => {
  await api.delete('/agent/history')
}
