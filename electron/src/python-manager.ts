import { spawn, ChildProcess, exec } from 'node:child_process'
import http from 'node:http'
import path from 'node:path'
import { app } from 'electron'
import type { PythonStatus } from './ipc-channels'
import { resolveCondaPython } from './utils'

export class PythonManager {
  private process: ChildProcess | null = null
  private port: number = 8000
  private _ready: boolean = false

  get ready(): boolean {
    return this._ready
  }

  /**
   * 解析 Python 可执行文件路径
   *
   * 优先级：
   *   1. 打包内置的 Python（extraResources 中的 PyInstaller 产物）
   *   2. conda 环境 safe-cli-agent 的 python
   *   3. 系统 PATH 中的 python
   */
  private resolvePython(): string {
    // 生产模式：优先用打包内置的 Python
    if (app.isPackaged) {
      return process.platform === 'win32'
        ? path.join(process.resourcesPath, 'python', 'python.exe')
        : path.join(process.resourcesPath, 'python', 'bin', 'python3')
    }

    // 开发模式：尝试 conda 环境
    const condaPython = resolveCondaPython()
    if (condaPython) return condaPython

    // 系统 PATH fallback
    return process.platform === 'win32' ? 'python' : 'python3'
  }

  /**
   * 等待后端就绪（轮询 health endpoint）
   */
  private waitForReady(timeoutMs: number = 15000): Promise<void> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now()

      const check = (): void => {
        const req = http.get(`http://localhost:${this.port}/health`, (res) => {
          if (res.statusCode === 200) {
            this._ready = true
            resolve()
            return
          }
          retry()
        })
        req.on('error', () => retry())
        req.setTimeout(1000, () => {
          req.destroy()
          retry()
        })
      }

      const retry = (): void => {
        if (Date.now() - startTime > timeoutMs) {
          reject(new Error(`后端启动超时 (${timeoutMs}ms)`))
          return
        }
        setTimeout(check, 500)
      }

      check()
    })
  }

  async start(): Promise<void> {
    const python = this.resolvePython()
    // 项目根目录（electron/../ — 即 cli-agent/ 根）
    const projectRoot = path.join(__dirname, '../..')

    console.log(`[PythonManager] 启动 Python 后端: ${python}`)
    console.log(`[PythonManager] 工作目录: ${projectRoot}`)

    this.process = spawn(python, ['-m', 'src.api.main'], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PORT: String(this.port),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    // 收集启动日志（出错时展示给用户）
    let startupLog = ''
    this.process.stdout?.on('data', (data: Buffer) => {
      const text = data.toString()
      startupLog += text
      if (startupLog.length > 5000) startupLog = startupLog.slice(-5000)
      process.stdout.write(`[python] ${text}`)
    })
    this.process.stderr?.on('data', (data: Buffer) => {
      const text = data.toString()
      startupLog += text
      if (startupLog.length > 5000) startupLog = startupLog.slice(-5000)
      process.stderr.write(`[python:err] ${text}`)
    })

    this.process.on('exit', (code: number | null) => {
      this._ready = false
      if (code !== 0 && code !== null) {
        console.error(`[PythonManager] Python 后端异常退出，退出码: ${code}`)
      }
    })

    try {
      await this.waitForReady()
      console.log(`[PythonManager] Python 后端已就绪 (端口: ${this.port})`)
    } catch (err: any) {
      const error = new Error(
        `${err.message}\n\n后端日志:\n${startupLog.slice(-2000)}`
      )
      throw error
    }
  }

  async stop(): Promise<void> {
    if (!this.process) return

    console.log('[PythonManager] 正在关闭 Python 后端...')

    return new Promise((resolve) => {
      if (process.platform === 'win32') {
        // Windows: 用 taskkill 杀掉整个进程树
        exec(`taskkill /pid ${this.process!.pid} /T /F`, () => {
          console.log('[PythonManager] Python 进程已终止')
          resolve()
        })
      } else {
        this.process!.kill('SIGTERM')

        const forceKillTimer = setTimeout(() => {
          if (this.process) {
            console.log('[PythonManager] 强制终止 Python 进程')
            this.process.kill('SIGKILL')
          }
        }, 5000)

        this.process!.on('exit', () => {
          clearTimeout(forceKillTimer)
          console.log('[PythonManager] Python 进程已退出')
          resolve()
        })
      }
    })
  }

  getStatus(): PythonStatus {
    return {
      running: this.process !== null && this._ready,
      pid: this.process?.pid ?? null,
      port: this.port,
    }
  }
}
