import api from './agent'
import type { PluginDetail, PluginActionResponse, ComposePluginInfo, SessionInfo } from '@/types'

export const getPlugins = async (): Promise<PluginDetail[]> => {
  const response = await api.get('/plugins')
  return response.data
}

export const startPlugin = async (name: string): Promise<PluginActionResponse> => {
  const response = await api.post(`/plugins/${name}/start`)
  return response.data
}

export const stopPlugin = async (name: string): Promise<PluginActionResponse> => {
  const response = await api.post(`/plugins/${name}/stop`)
  return response.data
}

export const resetPlugin = async (name: string): Promise<PluginActionResponse> => {
  const response = await api.post(`/plugins/${name}/reset`)
  return response.data
}

export const getComposes = async (): Promise<ComposePluginInfo[]> => {
  const response = await api.get('/composes')
  return response.data
}

export const executeCommandPlugin = async (name: string, command?: string): Promise<{ success: boolean; output?: string; message?: string }> => {
  const response = await api.post(`/command/${name}`, command ? { command } : {})
  return response.data
}

export const regenerateCompose = async (name: string): Promise<{ success: boolean; message?: string }> => {
  const response = await api.post(`/composes/${name}/regenerate`)
  return response.data
}

// ============================================================
// Session API（对话历史持久化）
// ============================================================

export const listSessions = async (): Promise<SessionInfo[]> => {
  const response = await api.get('/agent/sessions')
  return response.data
}

export const createSession = async (): Promise<{ session_id: string; tool_names: string[] }> => {
  const response = await api.post('/agent/sessions')
  return response.data
}

export const getSession = async (sessionId: string): Promise<any> => {
  const response = await api.get(`/agent/sessions/${sessionId}`)
  return response.data
}

export const deleteSession = async (sessionId: string): Promise<{ success: boolean }> => {
  const response = await api.delete(`/agent/sessions/${sessionId}`)
  return response.data
}

export const resumeSession = async (sessionId: string): Promise<{
  session_id: string;
  tool_names: string[];
  messages: any[];
}> => {
  const response = await api.post(`/agent/sessions/${sessionId}/resume`)
  return response.data
}

export const updateSessionTitle = async (sessionId: string, title: string): Promise<{ success: boolean }> => {
  const response = await api.post(`/agent/sessions/${sessionId}/title`, { title })
  return response.data
}

export const saveSessionMessage = async (sessionId: string, message: any): Promise<{ success: boolean }> => {
  const response = await api.post(`/agent/sessions/${sessionId}/message`, { message })
  return response.data
}

export const updateSessionToolNames = async (sessionId: string, toolNames: string[]): Promise<{ success: boolean }> => {
  console.log(`[API] updateSessionToolNames: sessionId=${sessionId}, toolNames=${toolNames}`)
  const response = await api.post(`/agent/sessions/${sessionId}/tools`, { tool_names: toolNames })
  console.log(`[API] updateSessionToolNames response:`, response.data)
  return response.data
}
