import { contextBridge, ipcRenderer } from 'electron'
import type { NotificationPayload, PythonStatus, PythonCrashedPayload } from './ipc-channels'

/**
 * 通过 contextBridge 暴露类型安全的 API 给 Renderer 进程（Vue 前端）
 *
 * 前端通过 window.electronAPI 访问这些方法
 * 如果 window.electronAPI 为 undefined，说明运行在浏览器而非 Electron 中
 */

export interface ElectronAPI {
  showNotification: (payload: NotificationPayload) => void
  getPythonStatus: () => Promise<PythonStatus>
  onPythonCrashed: (callback: (data: PythonCrashedPayload) => void) => void
  minimizeToTray: () => void
  quitApp: () => void
  platform: string
  openExternal: (url: string) => void
}

contextBridge.exposeInMainWorld('electronAPI', {
  // 系统通知
  showNotification: (payload: NotificationPayload): void => {
    ipcRenderer.send('show-notification', payload)
  },

  // Python 后端状态（invoke → handle 双向通信）
  getPythonStatus: (): Promise<PythonStatus> => {
    return ipcRenderer.invoke('get-python-status')
  },

  // 监听 Python 崩溃
  onPythonCrashed: (callback: (data: PythonCrashedPayload) => void): void => {
    ipcRenderer.on('python-crashed', (_event, data) => callback(data))
  },

  // 最小化到托盘
  minimizeToTray: (): void => {
    ipcRenderer.send('minimize-to-tray')
  },

  // 退出应用
  quitApp: (): void => {
    ipcRenderer.send('quit-app')
  },

  // 平台信息
  platform: process.platform as string,

  // 用默认浏览器打开链接
  openExternal: (url: string): void => {
    ipcRenderer.send('open-external', { url })
  },
} satisfies ElectronAPI)
