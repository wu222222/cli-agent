import { Tray, Menu, nativeImage, app } from 'electron'
import path from 'node:path'
import type { BrowserWindow } from 'electron'
import type { PythonManager } from './python-manager'

export function createTray(mainWindow: BrowserWindow, pythonManager: PythonManager): Tray {
  // 图标路径（electron-vite 编译后 out/main 相对于项目根）
  const iconPath = path.join(__dirname, '../../build/icon.png')
  const tray = new Tray(nativeImage.createFromPath(iconPath))

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

  // 每 5 秒更新状态显示
  setInterval(() => {
    tray.setContextMenu(buildMenu())
  }, 5000)

  return tray
}
