import { spawn, ChildProcess, exec, execSync } from 'node:child_process'
import http from 'node:http'
import type { IncomingMessage } from 'node:http'
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
            console.log(`[PythonManager] Released port ${port} (PID: ${pid})`)
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
    // 优先 conda 环境
    const condaPython = resolveCondaPython()
    if (condaPython) return condaPython

    // 系统 PATH
    return process.platform === 'win32' ? 'python' : 'python3'
  }

  /**
   * 等待后端就绪（轮询 health endpoint）
   */
  private waitForReady(timeoutMs: number = 15000): Promise<void> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now()
      let settled = false

      const check = (): void => {
        if (settled) return
        const req = http.get(`http://localhost:${this.port}/api/health`, (res: IncomingMessage) => {
          res.resume() // 消费响应体，释放 socket
          if (settled) { req.destroy(); return }
          if (res.statusCode === 200) {
            settled = true
            this._ready = true
            req.destroy()
            resolve()
            return
          }
          retry()
        })
        req.on('error', () => { if (!settled) retry() })
        req.setTimeout(1000, () => { req.destroy(); if (!settled) retry() })
      }

      const retry = (): void => {
        if (Date.now() - startTime > timeoutMs) {
          if (!settled) {
            settled = true
            reject(new Error(`Backend startup timeout (${timeoutMs}ms)`))
          }
          return
        }
        setTimeout(check, 500)
      }

      check()
    })
  }

  async start(): Promise<void> {
    const python = this.resolvePython()

    // 检查 Python 可执行文件是否存在
    if (!python || python === 'python' || python === 'python3') {
      // 系统 PATH 中的 python，不检查文件存在性
    } else {
      const fs = require('fs')
      if (!fs.existsSync(python)) {
        throw new Error(
          `Python 环境未找到: ${python}\n\n` +
          `请确保已安装 Python 3.10+ 并创建 conda 环境:\n` +
          `  conda create -n safe-cli-agent python=3.10\n` +
          `  conda activate safe-cli-agent\n` +
          `  pip install -r requirements.txt`
        )
      }
    }

    // 打包模式：Python 源码在 app.asar.unpack 中（asar 无法直接执行 Python）
    const projectRoot = app.isPackaged
      ? path.join(process.resourcesPath, 'app.asar.unpack')
      : path.join(__dirname, '../..')

    // Windows: 强制控制台使用 UTF-8 编码（解决中文乱码）
    if (process.platform === 'win32') {
      try {
        execSync('chcp 65001', { stdio: 'ignore' })
      } catch { /* ignore */ }
    }

    // 先释放端口（kill 之前残留的 Python 进程）
    this.killPort(this.port)
    // 等 200ms 让端口完全释放
    await new Promise(r => setTimeout(r, 200))

    console.log(`[PythonManager] Starting Python backend: ${python}`)
    console.log(`[PythonManager] Working directory: ${projectRoot}`)

    this.process = spawn(python, ['-X', 'utf8', '-m', 'src.api.main'], {
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

    // 收集启动日志（启动成功后停止收集，但保留 stdout/stderr 转发）
    let startupLog = ''
    let collecting = true
    const onStdout = (data: Buffer): void => {
      const text = data.toString('utf-8')
      if (collecting) {
        startupLog += text
        if (startupLog.length > 5000) startupLog = startupLog.slice(-5000)
      }
      process.stdout.write(`[python] ${text}`)
    }
    const onStderr = (data: Buffer): void => {
      const text = data.toString('utf-8')
      if (collecting) {
        startupLog += text
        if (startupLog.length > 5000) startupLog = startupLog.slice(-5000)
      }
      process.stderr.write(`[python:err] ${text}`)
    }

    this.process.stdout?.on('data', onStdout)
    this.process.stderr?.on('data', onStderr)

    this.process.on('exit', (code: number | null) => {
      this._ready = false
      console.log(`[PythonManager] Python backend exited with code: ${code}`)
      // 自动重启（无论退出码是什么，包括用户点击重启按钮触发的 exit(0)）
      setTimeout(() => {
        console.log('[PythonManager] Auto-restarting Python backend...')
        this.start().catch(err => {
          console.error('[PythonManager] Auto-restart failed:', err.message)
        })
      }, 1000)
    })

    try {
      await this.waitForReady()
      // 启动成功后停止收集 startupLog（stdout/stderr 转发保留）
      collecting = false
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
      // 5 秒超时，超时后强制 resolve（防止退出挂起）
      const forceTimer = setTimeout(() => {
        console.log('[PythonManager] Stop timeout, forcing exit')
        resolve()
      }, 5000)

      this.process!.once('exit', () => {
        clearTimeout(forceTimer)
        console.log('[PythonManager] Python process exited')
        resolve()
      })

      if (process.platform === 'win32') {
        exec(`taskkill /pid ${this.process!.pid} /T /F`, () => {
          // exit 事件会处理 resolve
        })
      } else {
        this.process!.kill('SIGTERM')
        setTimeout(() => {
          if (this.process) {
            console.log('[PythonManager] Force killing Python process')
            this.process.kill('SIGKILL')
          }
        }, 3000)
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
