export interface StepInfo {
  agent: string
  type: 'thinking' | 'tool_call' | 'tool_result' | 'final'
  content: string
  tool?: string
}

export interface Message {
  role: 'user' | 'system'
  content: string
  timestamp: string
  thought: string
  type: 'text' | 'code'
  agent?: string
  steps?: StepInfo[]
}

export interface ApiResponse {
  content: string
  thought?: string
  type: 'text' | 'confirm'
  agent?: string
  steps?: StepInfo[]
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

export interface DockerPreset {
  name: string
  image: string
  description: string
}

export interface DockerConfigForm {
  image: string
  container_name: string
  network: string
  memory_limit: string
  timeout: number
  use_host_workspace: boolean
  use_knowledge_base: boolean
  kb_mode: string
}
