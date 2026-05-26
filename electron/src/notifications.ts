import { Notification, ipcMain } from 'electron'
import type { BrowserWindow } from 'electron'
import type { NotificationPayload } from './ipc-channels'

export function setupNotifications(mainWindow: BrowserWindow): void {
  // 来自 Renderer 的 show-notification 请求
  ipcMain.on('show-notification', (_event, { title, body }: NotificationPayload) => {
    if (!Notification.isSupported()) {
      console.warn('[Notifications] 当前系统不支持 Notification API')
      return
    }

    const notification = new Notification({ title, body })

    // 点击通知 → 显示窗口
    notification.on('click', () => {
      mainWindow.show()
      mainWindow.focus()
    })

    notification.show()
  })
}
