/**
 * Electron API 类型声明
 * 与 electron/src/preload.ts 中 exposeInMainWorld 的类型保持一致
 *
 * 用法：
 *   if (window.electronAPI) {
 *     window.electronAPI.showNotification({ title: '...', body: '...' })
 *   }
 */

export interface NotificationPayload {
  title: string
  body: string
}

export interface PythonStatus {
  running: boolean
  pid: number | null
  port: number
}

export interface PythonCrashedPayload {
  exitCode: number
}

export interface ElectronAPI {
  showNotification: (payload: NotificationPayload) => void
  getPythonStatus: () => Promise<PythonStatus>
  onPythonCrashed: (callback: (data: PythonCrashedPayload) => void) => void
  minimizeToTray: () => void
  quitApp: () => void
  platform: string
  openExternal: (url: string) => void
}

// 扩展全局 Window 接口
declare global {
  interface Window {
    /** 仅在 Electron 环境中可用，浏览器中为 undefined */
    electronAPI?: ElectronAPI
  }
}

export {}
