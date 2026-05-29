<template>
  <div class="setup-container">
    <div class="setup-card">
      <!-- 关闭按钮 -->
      <button class="close-btn" @click="exitApp" title="退出应用">✕</button>

      <div class="setup-logo">🛡</div>
      <h1 class="setup-title">Safe-CLI-Agent</h1>
      <p class="setup-subtitle">环境配置</p>

      <!-- 环境检测 -->
      <div class="setup-checks">
        <div class="check-item" :class="dockerClass">
          <span class="check-icon">{{ dockerIcon }}</span>
          <span>{{ dockerLabel }}</span>
        </div>
        <div class="check-item" :class="status.configured ? 'ok' : 'pending'">
          <span class="check-icon">{{ status.configured ? '✓' : '○' }}</span>
          <span>API {{ status.configured ? '已配置' : '待配置' }}</span>
        </div>
      </div>

      <!-- Docker 提示 -->
      <div v-if="status.docker_status === 'not_installed'" class="setup-warning">
        <p>Docker 未安装。容器插件功能需要 Docker 支持。</p>
        <a href="https://www.docker.com/products/docker-desktop/" target="_blank" class="docker-link">
          下载 Docker Desktop →
        </a>
      </div>
      <div v-else-if="status.docker_status === 'not_running'" class="setup-warning warn-yellow">
        <p>Docker 已安装但未启动。请打开 Docker Desktop 启动服务。</p>
      </div>

      <!-- 环境变量来源提示 -->
      <div v-if="status.config_source === 'env'" class="setup-info">
        <p>检测到系统环境变量已配置，无需重复填写。</p>
      </div>
      <div v-else-if="status.config_source === 'partial'" class="setup-warning warn-yellow">
        <p>检测到部分配置，请补全以下必填项。</p>
      </div>

      <!-- 配置表单 -->
      <div class="setup-form">
        <div class="form-group">
          <label>API Key <span class="required">*</span></label>
          <input
            v-model="form.api_key"
            type="password"
            :placeholder="status.api_key || 'sk-xxxxxxxxxx'"
            class="form-input"
          />
          <span class="form-hint">
            <template v-if="status.config_source === 'env'">已从系统环境变量读取（留空则保留）</template>
            <template v-else>兼容 OpenAI 格式的 API Key</template>
          </span>
        </div>

        <div class="form-group">
          <label>Base URL</label>
          <input
            v-model="form.base_url"
            type="text"
            placeholder="https://api.openai.com/v1"
            class="form-input"
          />
          <span class="form-hint">兼容 OpenAI 格式的 API 地址</span>
        </div>

        <div class="form-group">
          <label>模型名称 <span class="required">*</span></label>
          <input
            v-model="form.model"
            type="text"
            :placeholder="status.model || 'gpt-4o'"
            class="form-input"
          />
          <span class="form-hint">如 gpt-4o、claude-sonnet-4-6、deepseek-chat 等</span>
        </div>

        <button
          class="setup-btn"
          @click="saveConfig"
          :disabled="saving"
        >
          {{ saving ? '保存中...' : '保存配置' }}
        </button>

        <p v-if="message" class="setup-message" :class="messageType">{{ message }}</p>
      </div>

      <!-- 跳过按钮 -->
      <button class="skip-btn" @click="skipSetup">
        {{ status.configured ? '进入主界面' : '跳过，直接进入' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/agent'

const router = useRouter()
const saving = ref(false)
const message = ref('')
const messageType = ref<'ok' | 'error'>('ok')

const status = ref({
  configured: false,
  has_env: false,
  docker_status: 'not_installed' as string,
  config_source: 'none' as string,
  api_key: '',
  base_url: '',
  model: '',
})

const form = ref({
  api_key: '',
  base_url: '',
  model: '',
})

const dockerClass = computed(() => {
  if (status.value.docker_status === 'running') return 'ok'
  if (status.value.docker_status === 'not_running') return 'warn'
  return 'fail'
})

const dockerIcon = computed(() => {
  if (status.value.docker_status === 'running') return '✓'
  if (status.value.docker_status === 'not_running') return '!'
  return '✕'
})

const dockerLabel = computed(() => {
  if (status.value.docker_status === 'running') return 'Docker 运行中'
  if (status.value.docker_status === 'not_running') return 'Docker 未启动'
  return 'Docker 未安装'
})

onMounted(async () => {
  try {
    const resp = await api.get('/setup/status')
    status.value = resp.data
    form.value.base_url = resp.data.base_url || form.value.base_url
    form.value.model = resp.data.model || ''
  } catch {
    // 后端未启动
  }
})

async function saveConfig() {
  saving.value = true
  message.value = ''
  try {
    const resp = await api.post('/setup/save', form.value)
    if (resp.data.success) {
      messageType.value = 'ok'
      message.value = resp.data.message
      // 更新状态
      status.value.configured = true
    } else {
      messageType.value = 'error'
      message.value = resp.data.message
    }
  } catch (e: any) {
    messageType.value = 'error'
    message.value = '保存失败: ' + (e.message || '未知错误')
  } finally {
    saving.value = false
  }
}

function skipSetup() {
  router.replace('/')
}

function exitApp() {
  window.electronAPI?.quitApp()
}
</script>

<style scoped>
.setup-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.setup-card {
  position: relative;
  width: 440px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  backdrop-filter: blur(20px);
  text-align: center;
}

.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.35);
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: #e81123;
  color: #fff;
}

.setup-logo {
  font-size: 48px;
  margin-bottom: 12px;
}

.setup-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
}

.setup-subtitle {
  margin: 4px 0 24px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.setup-checks {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 20px;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 8px;
}

.check-item.ok { background: rgba(103, 194, 58, 0.1); color: #67c23a; }
.check-item.fail { background: rgba(245, 108, 108, 0.1); color: #f56c6c; }
.check-item.warn { background: rgba(230, 162, 60, 0.1); color: #e6a23c; }
.check-item.pending { background: rgba(255, 255, 255, 0.05); color: rgba(255, 255, 255, 0.5); }

.check-icon { font-weight: bold; }

.setup-warning {
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: #f56c6c;
}

.setup-warning.warn-yellow {
  background: rgba(230, 162, 60, 0.1);
  border-color: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.setup-warning p { margin: 0 0 6px; }

.docker-link {
  color: #79bbff;
  text-decoration: none;
  font-size: 12px;
}

.docker-link:hover { text-decoration: underline; }

.setup-info {
  margin-bottom: 16px;
  padding: 10px 12px;
  background: rgba(103, 194, 58, 0.08);
  border: 1px solid rgba(103, 194, 58, 0.15);
  border-radius: 8px;
  font-size: 12px;
  color: #67c23a;
}

.setup-info p { margin: 0; }

.setup-form {
  text-align: left;
}

.form-group {
  margin-bottom: 14px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 6px;
}

.required { color: #f56c6c; }

.form-input {
  width: 100%;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-input:focus { border-color: #409eff; }
.form-input::placeholder { color: rgba(255, 255, 255, 0.3); }

.form-hint {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 4px;
}

.setup-btn {
  width: 100%;
  padding: 11px;
  margin-top: 4px;
  background: #409eff;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.setup-btn:hover:not(:disabled) { background: #66b1ff; }
.setup-btn:disabled { background: rgba(64, 158, 255, 0.4); cursor: not-allowed; }

.setup-message {
  margin-top: 10px;
  font-size: 13px;
  text-align: center;
}

.setup-message.ok { color: #67c23a; }
.setup-message.error { color: #f56c6c; }

.skip-btn {
  width: 100%;
  padding: 10px;
  margin-top: 16px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.skip-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.8);
}
</style>
