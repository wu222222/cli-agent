import api from './agent'
import type { PluginDetail, PluginActionResponse, ComposePluginInfo } from '@/types'

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
