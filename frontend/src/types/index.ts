export interface Message {
  role: 'user' | 'system'
  content: string
  timestamp: string
  thought: string
  type: 'text' | 'code'
}

export interface ApiResponse {
  content: string
  thought?: string
  type: 'text' | 'code' | 'confirm'
}

export interface Settings {
  apiUrl: string
  apiKey: string
  requireConfirmation: boolean
  enableNetwork: boolean
}

export interface ToolCall {
  type: string
  parameters: Record<string, unknown>
}