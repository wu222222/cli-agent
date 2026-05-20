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
export type ToolType = 'exec' | 'command' | 'network' | 'local'

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
  plugin_type: string  // exec / command / compose / local / network（唯一类型标识）
  agent_type: string   // worker / judge / curator / none
  container_name: string
  status: 'running' | 'stopped' | 'unknown' | 'registered' | 'pending'
  parent_compose?: string
  command_trigger?: string  // 仅 command 类型，如 "/summary"
  display_name?: string     // 前端/SSE 显示名
  // === 后端总是返回 ===
  bound_action?: string
  requires_confirmation?: boolean
  mount_dirs?: string[]
  parameters?: Record<string, { type: string; description: string }>
  required_params?: string[]
  category?: string
  icon?: string
}

export interface PluginDetail extends PluginInfo {
  image?: string
  entrypoint_cmd?: string
}

export interface ComposePluginInfo {
  name: string
  description: string
  compose_file: string
  running: boolean
  category: string
  icon: string
  children: PluginInfo[]
  has_regenerate: boolean  // 是否有 flag 重生成脚本
}

export interface PluginActionResponse {
  success: boolean
  message: string
}
