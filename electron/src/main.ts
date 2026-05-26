import {
  app,
  BrowserWindow,
  dialog,
  shell,
  ipcMain,
} from 'electron'
import path from 'node:path'
import { PythonManager } from './python-manager'
import { createTray } from './tray'
import { setupNotifications } from './notifications'
import { setupUpdater } from './updater'
import { checkDocker } from './utils'

// 扩展 Electron App 类型（Electron 原生不支持 isQuitting 属性）
declare module 'electron' {
  interface App {
    isQuitting?: boolean
  }
}

let mainWindow: BrowserWindow | null = null
let pythonManager: PythonManager

// ── 创建主窗口 ──────────────────────────────────────────

async function createWindow(): Promise<BrowserWindow> {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Safe-CLI-Agent',
    icon: path.join(__dirname, '../../build/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'), // electron-vite 编译产物
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false, // 等 ready-to-show 时显示，避免白屏
  })

  // 页面渲染完成后显示窗口
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  // 加载前端
  //   生产模式：Python 后端 serve 前端 dist (localhost:8000)
  //   开发模式：同样从 8000 加载（执行 npm run build:frontend 先构建前端）
  //   如需 Vite HMR：另开终端 npm run dev:frontend，并设置 USE_VITE_DEV=1
  const useViteDev = process.env.USE_VITE_DEV === '1'
  if (useViteDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadURL('http://localhost:8000')
  }

  // 关闭窗口 → 最小化到托盘（而非退出）
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      mainWindow?.hide()
    }
  })

  return mainWindow
}

// ── 注册 IPC Handlers ───────────────────────────────────

function registerIpcHandlers(): void {
  // Python 状态查询（invoke/handle 双向通信）
  ipcMain.handle('get-python-status', () => {
    return pythonManager.getStatus()
  })

  // 最小化到托盘
  ipcMain.on('minimize-to-tray', () => {
    mainWindow?.hide()
  })

  // 退出应用
  ipcMain.on('quit-app', () => {
    app.isQuitting = true
    app.quit()
  })

  // 用系统默认浏览器打开链接
  ipcMain.on('open-external', (_event, { url }: { url: string }) => {
    shell.openExternal(url)
  })
}

// ── App 生命周期 ────────────────────────────────────────

app.whenReady().then(async () => {
  registerIpcHandlers()

  // Docker 预检
  if (!checkDocker()) {
    const result = await dialog.showMessageBox({
      type: 'warning',
      title: 'Docker 未安装',
      message: 'Safe-CLI-Agent 需要 Docker 来运行安全沙盒环境。',
      detail: '请先安装 Docker Desktop 后再启动应用。',
      buttons: ['下载 Docker Desktop', '退出'],
      defaultId: 0,
    })
    if (result.response === 0) {
      await shell.openExternal('https://www.docker.com/products/docker-desktop/')
    }
    app.quit()
    return
  }

  // 启动 Python 后端
  pythonManager = new PythonManager()
  try {
    await pythonManager.start()
  } catch (err: any) {
    dialog.showErrorBox('后端启动失败', `无法启动 Python 服务：\n${err.message}`)
    app.quit()
    return
  }

  // 创建主窗口
  await createWindow()

  // 系统托盘
  createTray(mainWindow!, pythonManager)

  // 原生通知
  setupNotifications(mainWindow!)

  // 自动更新
  setupUpdater()

  // macOS: Dock 图标点击 → 重新显示窗口
  app.on('activate', () => {
    mainWindow?.show()
  })
})

// 退出前清理 Python 子进程
app.on('before-quit', async () => {
  app.isQuitting = true
  if (pythonManager) {
    try {
      await pythonManager.stop()
    } catch {
      // 忽略清理错误，确保退出
    }
  }
})

// 所有窗口关闭时退出（macOS 除外）
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
