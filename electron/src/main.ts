import {
  app,
  BrowserWindow,
  dialog,
  shell,
  ipcMain,
  Menu,
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
let pythonManager: PythonManager | null = null

// ── 创建主窗口 ──────────────────────────────────────────

// 隐藏默认菜单栏（File Edit View Window）
Menu.setApplicationMenu(null)

async function createWindow(): Promise<BrowserWindow> {
  // 图标路径：开发模式从项目根目录找，打包后从 resources 找
  const getIconPath = (): string => {
    const ext = process.platform === 'win32' ? '.ico' : '.png'
    if (app.isPackaged) {
      return path.join(process.resourcesPath, `icon${ext}`)
    }
    // electron-vite dev: __dirname = out/main/, 需要往上两级到项目根
    return path.join(__dirname, '../../build/icon' + ext)
  }
  const iconPath = getIconPath()

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Safe-CLI-Agent',
    icon: iconPath,
    frame: false,  // 无边框窗口，使用自定义标题栏
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

  // F12 切换开发者工具（所有模式可用）
  mainWindow.webContents.on('before-input-event', (_event, input) => {
    if (input.key === 'F12' && input.type === 'keyDown') {
      mainWindow?.webContents.toggleDevTools()
    }
  })

  // 关闭窗口 → 退出应用
  mainWindow.on('close', () => {
    app.isQuitting = true
  })

  return mainWindow
}

// ── 注册 IPC Handlers ───────────────────────────────────

function registerIpcHandlers(): void {
  // Python 状态查询（invoke/handle 双向通信）
  ipcMain.handle('get-python-status', () => {
    return pythonManager?.getStatus() ?? { running: false, pid: null, port: 8000 }
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

  // 窗口控制（自定义标题栏需要）
  ipcMain.on('window-minimize', () => mainWindow?.minimize())
  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.on('window-close', () => mainWindow?.close())

  // 获取窗口状态
  ipcMain.handle('window-is-maximized', () => mainWindow?.isMaximized() ?? false)
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
  createTray(mainWindow!, pythonManager!)

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
