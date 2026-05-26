import { createServer } from 'node:net'

/**
 * 查找可用端口（从 preferred 开始尝试，被占用则用系统随机端口）
 */
export function findFreePort(preferred: number = 8000): Promise<number> {
  return new Promise((resolve) => {
    const server = createServer()
    server.listen(preferred, () => {
      const port = (server.address() as { port: number }).port
      server.close(() => resolve(port))
    })
    server.on('error', () => {
      server.listen(0, () => {
        const port = (server.address() as { port: number }).port
        server.close(() => resolve(port))
      })
    })
  })
}

/**
 * 检查 Docker 是否可用
 */
export function checkDocker(): boolean {
  try {
    const { execSync } = require('node:child_process')
    execSync('docker info', { stdio: 'ignore', timeout: 5000 })
    return true
  } catch {
    return false
  }
}

/**
 * 尝试获取 conda 环境中的 Python 路径
 */
export function resolveCondaPython(): string | null {
  if (process.platform !== 'win32') return null

  const home = process.env.USERPROFILE || process.env.HOME || ''
  const candidates = [
    `${home}\\miniforge3\\envs\\safe-cli-agent\\python.exe`,
    `${home}\\anaconda3\\envs\\safe-cli-agent\\python.exe`,
    `${home}\\miniconda3\\envs\\safe-cli-agent\\python.exe`,
  ]

  const fs = require('node:fs')
  for (const p of candidates) {
    if (fs.existsSync(p)) return p
  }
  return null
}
