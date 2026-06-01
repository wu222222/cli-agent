import {
  app,
  BrowserWindow,
  dialog,
  shell,
  ipcMain,
  Menu,
} from 'electron'
import path from 'node:path'
import fs from 'node:fs'
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

// ── 创建 Python 配置窗口 ──────────────────────────────────

async function createPythonSetupWindow(errorMessage: string): Promise<BrowserWindow> {
  console.log('[Main] 创建 Python 配置窗口')

  const getIconPath = (): string => {
    const ext = process.platform === 'win32' ? '.ico' : '.png'
    if (app.isPackaged) {
      return path.join(process.resourcesPath, `icon${ext}`)
    }
    return path.join(__dirname, '../../build/icon' + ext)
  }

  const setupWindow = new BrowserWindow({
    width: 700,
    height: 650,
    resizable: false,
    title: 'Safe-CLI-Agent - Python 环境配置',
    icon: getIconPath(),
    show: false, // 先隐藏，加载完成后显示
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // 加载本地 HTML 文件
  const htmlPath = app.isPackaged
    ? path.join(process.resourcesPath, 'app.asar.unpacked', 'electron', 'resources', 'python-setup.html')
    : path.join(__dirname, '../resources/python-setup.html')

  console.log('[Main] 加载配置界面:', htmlPath)
  await setupWindow.loadFile(htmlPath)

  // 等待页面完全加载后再发送错误信息
  setupWindow.webContents.on('did-finish-load', () => {
    console.log('[Main] 页面加载完成，发送错误信息')
    // 延迟一点时间确保 preload 脚本已执行
    setTimeout(() => {
      setupWindow.webContents.send('set-error-message', errorMessage)
    }, 500)
  })

  // 直接显示窗口，不等待 ready-to-show
  setupWindow.show()
  setupWindow.focus()

  // 开发模式下自动打开开发者工具
  if (!app.isPackaged) {
    setupWindow.webContents.openDevTools({ mode: 'detach' })
  }

  return setupWindow
}

// ── 注册 IPC Handlers ───────────────────────────────────

function registerIpcHandlers(): void {
  // Python 状态查询（invoke/handle 双向通信）
  ipcMain.handle('get-python-status', () => {
    return pythonManager?.getStatus() ?? { running: false, pid: null, port: 8000 }
  })

  // 检测可用的 Python 路径
  ipcMain.handle('detect-python-paths', async () => {
    console.log('[Main] 开始检测 Python 路径...')
    const { execSync } = require('child_process')
    const fs = require('fs')
    const pathModule = require('path')
    const paths: any[] = []

    // 1. Conda 环境
    try {
      console.log('[Main] 检测 conda 环境...')

      // 尝试多个可能的 conda 路径
      const condaPaths = [
        'conda',
        `${process.env.USERPROFILE || ''}\\anaconda3\\Scripts\\conda.exe`,
        `${process.env.USERPROFILE || ''}\\miniconda3\\Scripts\\conda.exe`,
        `${process.env.ProgramData || ''}\\anaconda3\\Scripts\\conda.exe`,
        `${process.env.ProgramData || ''}\\miniconda3\\Scripts\\conda.exe`,
      ]

      let condaOutput = ''
      let condaFound = false

      for (const condaCmd of condaPaths) {
        try {
          condaOutput = execSync(`"${condaCmd}" env list --json`, {
            encoding: 'utf-8',
            timeout: 8000,
            stdio: ['ignore', 'pipe', 'ignore']
          })
          condaFound = true
          console.log(`[Main] 使用 conda: ${condaCmd}`)
          break
        } catch {
          continue
        }
      }

      if (condaFound && condaOutput) {
        const envData = JSON.parse(condaOutput)
        console.log('[Main] 找到 conda 环境:', envData.envs?.length || 0)

        for (const envPath of envData.envs || []) {
          const envName = pathModule.basename(envPath)
          const pythonExe = process.platform === 'win32'
            ? `${envPath}\\python.exe`
            : `${envPath}/bin/python`
          if (fs.existsSync(pythonExe)) {
            let hasFastapi = false
            try {
              execSync(`"${pythonExe}" -c "import fastapi"`, {
                stdio: 'ignore',
                timeout: 3000
              })
              hasFastapi = true
            } catch {}
            paths.push({
              path: pythonExe,
              source: `conda (${envName})`,
              has_fastapi: hasFastapi,
              recommended: envName === 'safe-cli-agent',
            })
            console.log(`[Main] 发现环境: ${envName} - ${hasFastapi ? '有 fastapi' : '无 fastapi'}`)
          }
        }
      } else {
        console.warn('[Main] conda 未找到')
      }
    } catch (err) {
      console.warn('[Main] conda 检测失败:', err)
    }

    // 2. 系统 Python
    try {
      console.log('[Main] 检测系统 Python...')
      const sysPython = process.platform === 'win32' ? 'python' : 'python3'
      const whereCmd = process.platform === 'win32' ? 'where' : 'which'
      const sysPath = execSync(`${whereCmd} ${sysPython}`, {
        encoding: 'utf-8',
        timeout: 5000,
        stdio: ['ignore', 'pipe', 'ignore']
      }).trim().split(/\r?\n/)[0]

      if (sysPath && fs.existsSync(sysPath)) {
        let hasFastapi = false
        try {
          execSync(`"${sysPath}" -c "import fastapi"`, {
            stdio: 'ignore',
            timeout: 3000
          })
          hasFastapi = true
        } catch {}
        paths.push({
          path: sysPath,
          source: '系统 PATH',
          has_fastapi: hasFastapi,
          recommended: false,
        })
        console.log(`[Main] 系统 Python: ${sysPath} - ${hasFastapi ? '有 fastapi' : '无 fastapi'}`)
      }
    } catch (err) {
      console.warn('[Main] 系统 Python 检测失败:', err)
    }

    // 3. 常见路径检查
    const commonPaths = [
      `${process.env.USERPROFILE || ''}\\anaconda3\\envs\\safe-cli-agent\\python.exe`,
      `${process.env.USERPROFILE || ''}\\miniconda3\\envs\\safe-cli-agent\\python.exe`,
    ]

    for (const pythonPath of commonPaths) {
      if (fs.existsSync(pythonPath) && !paths.find(p => p.path === pythonPath)) {
        let hasFastapi = false
        try {
          execSync(`"${pythonPath}" -c "import fastapi"`, {
            stdio: 'ignore',
            timeout: 3000
          })
          hasFastapi = true
        } catch {}
        paths.push({
          path: pythonPath,
          source: '常见路径',
          has_fastapi: hasFastapi,
          recommended: true,
        })
        console.log(`[Main] 常见路径: ${pythonPath} - ${hasFastapi ? '有 fastapi' : '无 fastapi'}`)
      }
    }

    console.log(`[Main] 检测完成，共找到 ${paths.length} 个 Python 环境`)
    return paths
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
    console.error('[Main] Python 启动失败:', err.message)

    // 显示 Python 配置窗口
    const setupWindow = await createPythonSetupWindow(err.message)

    // 监听重启 Python 的请求
    ipcMain.on('restart-python', async () => {
      console.log('[Main] 收到重启 Python 请求')
      try {
        // 重新创建 PythonManager 并启动
        pythonManager = new PythonManager()
        await pythonManager.start()

        // 启动成功，关闭配置窗口，打开主窗口
        setupWindow.close()
        await createWindow()
        createTray(mainWindow!, pythonManager!)
        setupNotifications(mainWindow!)
        setupUpdater()
      } catch (retryErr: any) {
        console.error('[Main] Python 重启失败:', retryErr.message)
        setupWindow.webContents.send('set-error-message', retryErr.message)
      }
    })

    // 监听保存 Python 路径的请求（直接保存到本地文件）
    ipcMain.on('save-python-path', (_event, pythonPath: string) => {
      console.log('[Main] 保存 Python 路径:', pythonPath)
      const configPath = app.isPackaged
        ? path.join(process.resourcesPath, 'app.asar.unpacked', 'config', 'electron-config.json')
        : path.join(__dirname, '../../config/electron-config.json')

      const configDir = path.dirname(configPath)
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true })
      }

      let config: any = {}
      if (fs.existsSync(configPath)) {
        try {
          config = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
        } catch {}
      }

      config.python_path = pythonPath
      fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8')
      console.log('[Main] Python 路径已保存到:', configPath)
    })

    // 监听浏览文件请求
    ipcMain.on('browse-python-path', async (event) => {
      const result = await dialog.showOpenDialog({
        title: '选择 Python 可执行文件',
        filters: [
          { name: 'Python', extensions: ['exe'] },
          { name: 'All Files', extensions: ['*'] }
        ],
        properties: ['openFile']
      })

      if (!result.canceled && result.filePaths.length > 0) {
        event.sender.send('python-path-selected', result.filePaths[0])
      }
    })

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
