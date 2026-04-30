import axios from 'axios'
import type { ApiResponse } from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

export const sendMessage = async (message: string, confirmed: boolean = false): Promise<ApiResponse> => {
  const response = await api.post('/agent/chat', {
    message,
    confirmed
  })
  return response.data
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