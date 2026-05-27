import { createServer } from 'node:net'
import { execSync } from 'node:child_process'
import fs from 'node:fs'

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
    execSync('docker info', { stdio: 'ignore', timeout: 5000 })
    return true
  } catch {
    return false
  }
}

/**
 * 尝试获取 conda 环境的 Python 路径
 *
 * 策略（按优先级）：
 *   1. CONDA_PREFIX 环境变量（如果已激活）
 *   2. 常见安装路径 + envs/safe-cli-agent/python.exe
 *   3. 使用 conda run 检测（通过 PATH 中的 conda）
 */
export function resolveCondaPython(): string | null {
  const envName = 'safe-cli-agent'

  // 1. 检查 CONDA_PREFIX 环境变量
  const condaPrefix = process.env.CONDA_PREFIX
  if (condaPrefix && fs.existsSync(`${condaPrefix}\\python.exe`)) {
    if (condaPrefix.endsWith(`\\${envName}`) || condaPrefix.includes(`envs\\${envName}`)) {
      return `${condaPrefix}\\python.exe`
    }
  }

  // 2. 常见安装路径
  if (process.platform === 'win32') {
    const home = process.env.USERPROFILE || process.env.HOME || ''
    const candidates = [
      `${home}\\miniforge3\\envs\\${envName}\\python.exe`,
      `${home}\\anaconda3\\envs\\${envName}\\python.exe`,
      `${home}\\miniconda3\\envs\\${envName}\\python.exe`,
      `${home}\\AppData\\Local\\miniforge3\\envs\\${envName}\\python.exe`,
      `${home}\\mambaforge\\envs\\${envName}\\python.exe`,
    ]
    for (const p of candidates) {
      if (fs.existsSync(p)) return p
    }
  }

  // 3. 尝试用 conda run 获取 Python 路径
  try {
    const result = execSync(
      `conda run -n ${envName} python -c "import sys; print(sys.executable)"`,
      { encoding: 'utf-8', timeout: 10000, stdio: ['ignore', 'pipe', 'pipe'] }
    ).trim()
    if (result && fs.existsSync(result)) return result
  } catch {
    // conda 不可用或环境不存在
  }

  return null
}
