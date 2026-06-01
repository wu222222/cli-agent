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
  // 窗口控制（自定义标题栏）
  windowMinimize: () => void
  windowMaximize: () => void
  windowClose: () => void
  windowIsMaximized: () => Promise<boolean>
  // Python 配置相关
  savePythonPath: (path: string) => void
  restartPython: () => void
  browsePythonPath: () => void
  onPythonPathSelected: (callback: (path: string) => void) => void
  onSetErrorMessage: (callback: (message: string) => void) => void
  detectPythonPaths: () => Promise<any[]>
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

  // 监听 Python 崩溃（每次调用先移除旧监听，防止累积）
  onPythonCrashed: (callback: (data: PythonCrashedPayload) => void): void => {
    ipcRenderer.removeAllListeners('python-crashed')
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

  // 窗口控制（自定义标题栏）
  windowMinimize: (): void => {
    ipcRenderer.send('window-minimize')
  },
  windowMaximize: (): void => {
    ipcRenderer.send('window-maximize')
  },
  windowClose: (): void => {
    ipcRenderer.send('window-close')
  },
  windowIsMaximized: (): Promise<boolean> => {
    return ipcRenderer.invoke('window-is-maximized')
  },

  // Python 配置相关
  savePythonPath: (path: string): void => {
    ipcRenderer.send('save-python-path', path)
  },
  restartPython: (): void => {
    ipcRenderer.send('restart-python')
  },
  browsePythonPath: (): void => {
    ipcRenderer.send('browse-python-path')
  },
  onPythonPathSelected: (callback: (path: string) => void): void => {
    ipcRenderer.removeAllListeners('python-path-selected')
    ipcRenderer.on('python-path-selected', (_event, path) => callback(path))
  },
  onSetErrorMessage: (callback: (message: string) => void): void => {
    ipcRenderer.removeAllListeners('set-error-message')
    ipcRenderer.on('set-error-message', (_event, message) => callback(message))
  },
  detectPythonPaths: (): Promise<any[]> => {
    return ipcRenderer.invoke('detect-python-paths')
  },
} satisfies ElectronAPI)
