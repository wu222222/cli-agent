import { Tray, Menu, nativeImage, app } from 'electron'
import path from 'node:path'
import type { BrowserWindow } from 'electron'
import type { PythonManager } from './python-manager'

export function createTray(mainWindow: BrowserWindow, pythonManager: PythonManager): Tray {
  const iconPath = path.join(__dirname, '../../build/icon.png')
  const tray = new Tray(nativeImage.createFromPath(iconPath))

  let lastReady: boolean | null = null  // 记录上次状态，避免冗余重建
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  const buildMenu = (): Menu => {
    const statusLabel = pythonManager.ready ? '后端运行中' : '后端启动中...'
    return Menu.buildFromTemplate([
      {
        label: '显示主窗口',
        click: (): void => {
          mainWindow.show()
          mainWindow.focus()
        },
      },
      {
        label: `状态: ${statusLabel}`,
        enabled: false,
      },
      { type: 'separator' },
      {
        label: '退出 Safe-CLI-Agent',
        click: (): void => {
          app.isQuitting = true
          app.quit()
        },
      },
    ])
  }

  const refreshMenu = (): void => {
    const current = pythonManager.ready
    if (current !== lastReady) {
      lastReady = current
      tray.setContextMenu(buildMenu())
    }
  }

  tray.setToolTip('Safe-CLI-Agent')
  tray.setContextMenu(buildMenu())

  // 左键托盘 → 显示/隐藏窗口
  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide()
    } else {
      mainWindow.show()
      mainWindow.focus()
    }
  })

  // 每 5 秒检测状态变化（仅状态真正变化时才重建菜单）
  refreshTimer = setInterval(refreshMenu, 5000)

  // App 退出时清除 timer
  app.on('before-quit', () => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  })

  return tray
}
