import { spawn, ChildProcess, exec, execSync } from 'node:child_process'
import http from 'node:http'
import type { IncomingMessage } from 'node:http'
import path from 'node:path'
import fs from 'node:fs'
import { app } from 'electron'
import type { PythonStatus } from './ipc-channels'
import { resolveCondaPython } from './utils'

export class PythonManager {
  private process: ChildProcess | null = null
  private port: number = 8000
  private _ready: boolean = false
  private _restartCount: number = 0
  private static MAX_RESTARTS = 3

  /**
   * 读取配置文件中的 Python 路径
   */
  private getSavedPythonPath(): string | null {
    try {
      const configPath = app.isPackaged
        ? path.join(process.resourcesPath, 'app.asar.unpack', 'config', 'electron-config.json')
        : path.join(__dirname, '../../config/electron-config.json')

      if (fs.existsSync(configPath)) {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
        if (config.python_path && fs.existsSync(config.python_path)) {
          return config.python_path
        }
      }
    } catch (err) {
      console.warn('[PythonManager] 读取配置文件失败:', err)
    }
    return null
  }

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
   *   1. 用户配置的 Python 路径（config/electron-config.json）
   *   2. conda 环境 safe-cli-agent 的 python
   *   3. 系统 PATH 中的 python
   */
  private resolvePython(): string {
    // 1. 优先使用用户配置的 Python 路径
    const savedPath = this.getSavedPythonPath()
    if (savedPath) {
      console.log(`[PythonManager] 使用配置的 Python 路径: ${savedPath}`)
      return savedPath
    }

    // 2. 优先 conda 环境
    const condaPython = resolveCondaPython()
    if (condaPython) return condaPython

    // 3. 系统 PATH — 验证 fastapi 是否可用
    const sysPython = process.platform === 'win32' ? 'python' : 'python3'
    try {
      const { execSync } = require('child_process')
      execSync(`${sysPython} -c "import fastapi"`, { stdio: 'ignore', timeout: 5000 })
      return sysPython
    } catch {
      // 系统 Python 没有 fastapi，返回 conda 路径让 start() 报错
      console.error('[PythonManager] 系统 Python 缺少 fastapi，请激活 safe-cli-agent 环境')
      return sysPython
    }
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

    // 尝试启动 Python，如果 conda Python 失败则回退到系统 Python
    let actualPython = python
    const spawnOptions = {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONUTF8: '1',            // PEP 540: 强制 UTF-8 模式
        PYTHONIOENCODING: 'utf-8',  // 修复 Windows 中文乱码
        PYTHONLEGACYWINDOWSSTDIO: 'utf-8',
        PORT: String(this.port),
      },
      stdio: ['ignore', 'pipe', 'pipe'] as ['ignore', 'pipe', 'pipe'],
    }

    const args = ['-X', 'utf8', '-m', 'src.api.main']

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

    const onExit = (code: number | null): void => {
      this._ready = false
      console.log(`[PythonManager] Python backend exited with code: ${code}`)

      // 退出码 0 = 用户主动重启，直接重启
      if (code === 0) {
        this._restartCount = 0
        setTimeout(() => {
          this.start().catch(err => {
            console.error('[PythonManager] Restart failed:', err.message)
          })
        }, 1000)
        return
      }

      // 非 0 退出 = 启动失败，限制重试次数
      this._restartCount++
      if (this._restartCount <= PythonManager.MAX_RESTARTS) {
        console.log(`[PythonManager] Auto-restarting (${this._restartCount}/${PythonManager.MAX_RESTARTS})...`)
        setTimeout(() => {
          this.start().catch(err => {
            console.error('[PythonManager] Auto-restart failed:', err.message)
          })
        }, 2000)
      } else {
        console.error(`[PythonManager] 已重试 ${PythonManager.MAX_RESTARTS} 次仍失败，停止自动重启`)
        this._restartCount = 0
      }
    }

    // 绑定进程事件的辅助函数
    const bindProcessEvents = (proc: ChildProcess): void => {
      proc.stdout?.on('data', onStdout)
      proc.stderr?.on('data', onStderr)
      proc.on('exit', onExit)
    }

    // 如果是 conda 路径（非系统 python），先尝试启动
    this.process = spawn(actualPython, args, spawnOptions)
    bindProcessEvents(this.process)

    // 监听 error 事件，处理 ENOENT（文件不存在）错误
    this.process.on('error', (err: NodeJS.ErrnoException) => {
      if (err.code === 'ENOENT' && actualPython !== 'python' && actualPython !== 'python3') {
        console.warn(`[PythonManager] conda Python not accessible: ${actualPython}`)
        console.warn(`[PythonManager] Falling back to system Python`)
        console.warn(`[PythonManager] 如果系统 Python 缺少依赖，请运行: pip install -r requirements.txt`)
        actualPython = process.platform === 'win32' ? 'python' : 'python3'
        this.process = spawn(actualPython, args, spawnOptions)
        bindProcessEvents(this.process)
        this.process.on('error', (retryErr) => {
          console.error(`[PythonManager] System Python also failed:`, retryErr.message)
          this._ready = false
        })
      }
    })

    try {
      await this.waitForReady()
      // 启动成功后停止收集 startupLog（stdout/stderr 转发保留）
      collecting = false
      console.log(`[PythonManager] Python backend ready (port: ${this.port})`)
    } catch (err: any) {
      // 检查是否是依赖缺失问题
      const isMissingDeps = startupLog.includes('ModuleNotFoundError') ||
        startupLog.includes('No module named')

      let hint = ''
      if (isMissingDeps) {
        hint = `\n\n解决方案：
1. 激活 conda 环境后重新启动应用：
   conda activate safe-cli-agent

2. 或在系统 Python 中安装依赖：
   pip install -r requirements.txt`
      }

      const error = new Error(
        `${err.message}${hint}\n\nBackend logs:\n${startupLog.slice(-2000)}`
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
