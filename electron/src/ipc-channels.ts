// 所有 IPC 通道的请求/响应类型集中定义
// 保证 Main ↔ Renderer（preload）类型一致

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

// IPC 通道映射 — 编译时 + 运行时无额外开销（纯类型）
export interface IpcChannelMap {
  'show-notification': { input: NotificationPayload; output: void }
  'get-python-status': { input: void; output: PythonStatus }
  'python-crashed': { input: PythonCrashedPayload; output: void }
  'minimize-to-tray': { input: void; output: void }
  'quit-app': { input: void; output: void }
  'open-external': { input: { url: string }; output: void }
}

export type IpcChannel = keyof IpcChannelMap
