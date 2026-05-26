import { spawn, ChildProcess, exec, execSync } from 'node:child_process'
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
   * Windows: 杀掉占用指定端口的进程，解决 "端口被占用" 问题
   */
  private killPort(port: number): void {
    if (process.platform !== 'win32') {
      try {
        execSync(`lsof -ti :${port} | xargs kill -9 2>/dev/null`, { stdio: 'ignore' })
      } catch { /* 端口空闲则忽略 */ }
      return
    }

    try {
      const output = execSync(`netstat -ano | findstr :${port}`, {
        encoding: 'utf-8',
        timeout: 3000,
      })
      const lines = output.trim().split('\n')
      const killed = new Set<string>()
      for (const line of lines) {
        const parts = line.trim().split(/\s+/)
        const pid = parts[parts.length - 1]
        if (pid && pid !== '0' && !killed.has(pid)) {
          try {
            execSync(`taskkill /PID ${pid} /F /T`, { stdio: 'ignore' })
            killed.add(pid)
            console.log(`[PythonManager] 已释放端口 ${port} (PID: ${pid})`)
          } catch { /* 忽略 kill 失败 */ }
        }
      }
    } catch {
      // netstat 未找到匹配 → 端口空闲，无需处理
    }
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
    if (app.isPackaged) {
      return process.platform === 'win32'
        ? path.join(process.resourcesPath, 'python', 'python.exe')
        : path.join(process.resourcesPath, 'python', 'bin', 'python3')
    }

    const condaPython = resolveCondaPython()
    if (condaPython) return condaPython

    return process.platform === 'win32' ? 'python' : 'python3'
  }

  /**
   * 等待后端就绪（轮询 health endpoint）
   */
  private waitForReady(timeoutMs: number = 15000): Promise<void> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now()

      const check = (): void => {
        const req = http.get(`http://localhost:${this.port}/api/health`, (res) => {
          if (res.statusCode === 200) {
            this._ready = true
            resolve()
            return
          }
          retry()
        })
        req.on('error', () => retry())
        req.setTimeout(1000, () => { req.destroy(); retry() })
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
    const projectRoot = path.join(__dirname, '../..')

    // 先释放端口（kill 之前残留的 Python 进程）
    this.killPort(this.port)
    // 等 200ms 让端口完全释放
    await new Promise(r => setTimeout(r, 200))

    console.log(`[PythonManager] Starting Python backend: ${python}`)
    console.log(`[PythonManager] Working directory: ${projectRoot}`)

    this.process = spawn(python, ['-m', 'src.api.main'], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONUTF8: '1',            // PEP 540: 强制 UTF-8 模式
        PYTHONIOENCODING: 'utf-8',  // 修复 Windows 中文乱码
        PYTHONLEGACYWINDOWSSTDIO: 'utf-8',
        PORT: String(this.port),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    // 收集启动日志
    let startupLog = ''
    this.process.stdout?.on('data', (data: Buffer) => {
      const text = data.toString('utf-8')
      startupLog += text
      if (startupLog.length > 5000) startupLog = startupLog.slice(-5000)
      process.stdout.write(`[python] ${text}`)
    })
    this.process.stderr?.on('data', (data: Buffer) => {
      const text = data.toString('utf-8')
      startupLog += text
      if (startupLog.length > 5000) startupLog = startupLog.slice(-5000)
      process.stderr.write(`[python:err] ${text}`)
    })

    this.process.on('exit', (code: number | null) => {
      this._ready = false
      if (code !== 0 && code !== null) {
        console.error(`[PythonManager] Python backend exited with code: ${code}`)
      }
    })

    try {
      await this.waitForReady()
      console.log(`[PythonManager] Python backend ready (port: ${this.port})`)
    } catch (err: any) {
      const error = new Error(
        `${err.message}\n\nBackend logs:\n${startupLog.slice(-2000)}`
      )
      throw error
    }
  }

  async stop(): Promise<void> {
    if (!this.process) return

    console.log('[PythonManager] Stopping Python backend...')

    return new Promise((resolve) => {
      if (process.platform === 'win32') {
        exec(`taskkill /pid ${this.process!.pid} /T /F`, () => {
          console.log('[PythonManager] Python process terminated')
          resolve()
        })
      } else {
        this.process!.kill('SIGTERM')
        const forceKillTimer = setTimeout(() => {
          if (this.process) {
            console.log('[PythonManager] Force killing Python process')
            this.process.kill('SIGKILL')
          }
        }, 5000)

        this.process!.on('exit', () => {
          clearTimeout(forceKillTimer)
          console.log('[PythonManager] Python process exited')
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
