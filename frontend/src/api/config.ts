import axios from 'axios'
import type { DockerPreset, DockerConfigForm } from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

interface DockerConfigResponse {
  presets: DockerPreset[]
  current: DockerConfigForm
}

export const getDockerConfig = async (): Promise<DockerConfigResponse> => {
  const response = await api.get('/config/docker')
  return response.data
}

export const updateDockerConfig = async (config: DockerConfigForm): Promise<DockerConfigForm> => {
  const response = await api.post('/config/docker', config)
  return response.data
}
