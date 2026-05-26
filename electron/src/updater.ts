import { autoUpdater } from 'electron-updater'
import { dialog } from 'electron'

export function setupUpdater(): void {
  // 启动时检查一次
  autoUpdater.checkForUpdatesAndNotify()

  // 每 4 小时检查一次
  setInterval(() => {
    autoUpdater.checkForUpdatesAndNotify()
  }, 4 * 60 * 60 * 1000)

  autoUpdater.on('update-available', () => {
    dialog.showMessageBox({
      type: 'info',
      title: '更新可用',
      message: '发现新版本，将在后台自动下载...',
    })
  })

  autoUpdater.on('update-downloaded', () => {
    dialog
      .showMessageBox({
        type: 'info',
        title: '更新已下载',
        message: '新版本已下载完成，是否立即重启安装？',
        buttons: ['立即重启', '稍后'],
      })
      .then((result) => {
        if (result.response === 0) {
          autoUpdater.quitAndInstall()
        }
      })
  })

  autoUpdater.on('error', (err) => {
    console.error('[Updater] 更新检查失败:', err.message)
  })
}
