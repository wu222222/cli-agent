import api from './agent'
import type { PluginDetail, PluginActionResponse } from '@/types'

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
