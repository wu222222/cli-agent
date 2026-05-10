export interface StepInfo {
  agent: string
  type: 'thinking' | 'tool_call' | 'tool_result' | 'final'
  content: string
  tool?: string
}

export interface ToolEventData {
  agent: string
  tool: string
  content: string
  tool_type?: string
}

export type ToolStatus = 'running' | 'completed' | 'error'
export type ToolType = 'exec' | 'network' | 'local'

export interface ToolCardState {
  id: string
  toolName: string
  toolType: ToolType
  status: ToolStatus
  startTime: string
  endTime?: string
  startContent: string
  resultContent?: string
  agent: string
  params?: Record<string, unknown>
}

export interface Message {
  role: 'user' | 'system'
  content: string
  timestamp: string
  thought: string
  type: 'text' | 'code' | 'tool_card' | 'thought' | 'tool_result'
  agent?: string
  steps?: StepInfo[]
  toolState?: ToolCardState
  toolName?: string
  command?: string
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

export interface PluginInfo {
  name: string
  description: string
  tool_type: string
  plugin_type: string  // exec / command / local
  container_name: string
  status: 'running' | 'stopped' | 'unknown'
}

export interface PluginDetail extends PluginInfo {
  bound_action?: string
  requires_confirmation?: boolean
  image?: string
  entrypoint_cmd?: string
  mount_dirs?: string[]
  parameters?: Record<string, { type: string; description: string }>
  required_params?: string[]
  category?: string
  icon?: string
}

export interface PluginActionResponse {
  success: boolean
  message: string
}
