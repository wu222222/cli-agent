<template>
  <div class="setup-container">
    <div class="setup-card">
      <div class="setup-logo">🛡</div>
      <h1 class="setup-title">Safe-CLI-Agent</h1>
      <p class="setup-subtitle">首次启动配置</p>

      <!-- 环境检测 -->
      <div class="setup-checks">
        <div class="check-item" :class="status.docker_ok ? 'ok' : 'fail'">
          <span class="check-icon">{{ status.docker_ok ? '✓' : '✕' }}</span>
          <span>Docker {{ status.docker_ok ? '已安装' : '未安装' }}</span>
        </div>
        <div class="check-item" :class="status.configured ? 'ok' : 'pending'">
          <span class="check-icon">{{ status.configured ? '✓' : '○' }}</span>
          <span>API 配置 {{ status.configured ? '已完成' : '待配置' }}</span>
        </div>
      </div>

      <!-- Docker 未安装提示 -->
      <div v-if="!status.docker_ok" class="setup-warning">
        <p>Docker 未检测到。部分功能（容器插件）需要 Docker 支持。</p>
        <a href="https://www.docker.com/products/docker-desktop/" target="_blank" class="docker-link">
          下载 Docker Desktop →
        </a>
      </div>

      <!-- 配置表单 -->
      <div class="setup-form">
        <div class="form-group">
          <label>API Key <span class="required">*</span></label>
          <input
            v-model="form.api_key"
            type="password"
            placeholder="sk-xxxxxxxxxx"
            class="form-input"
          />
          <span class="form-hint">DashScope API Key（阿里云通义千问）</span>
        </div>

        <div class="form-group">
          <label>Base URL</label>
          <input
            v-model="form.base_url"
            type="text"
            placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
            class="form-input"
          />
          <span class="form-hint">兼容 OpenAI 格式的 API 地址</span>
        </div>

        <div class="form-group">
          <label>模型名称 <span class="required">*</span></label>
          <input
            v-model="form.model"
            type="text"
            placeholder="qwen3.6-flash"
            class="form-input"
          />
          <span class="form-hint">如 qwen3.6-flash、gpt-4o、deepseek-chat 等</span>
        </div>

        <button
          class="setup-btn"
          @click="saveConfig"
          :disabled="saving || !form.api_key || !form.model"
        >
          {{ saving ? '保存中...' : '保存并开始使用' }}
        </button>

        <p v-if="message" class="setup-message" :class="messageType">{{ message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/agent'

const router = useRouter()
const saving = ref(false)
const message = ref('')
const messageType = ref<'ok' | 'error'>('ok')

const status = ref({
  configured: false,
  has_env: false,
  docker_ok: false,
  api_key: '',
  base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  model: '',
})

const form = ref({
  api_key: '',
  base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  model: '',
})

onMounted(async () => {
  try {
    const resp = await api.get('/setup/status')
    status.value = resp.data
    form.value.base_url = resp.data.base_url || form.value.base_url
    form.value.model = resp.data.model || ''
    // 如果已配置，直接跳转
    if (resp.data.configured) {
      router.replace('/')
    }
  } catch {
    // 后端未启动，保持在引导页
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
      // 2 秒后跳转
      setTimeout(() => router.replace('/'), 2000)
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
  width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  backdrop-filter: blur(20px);
  text-align: center;
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
  gap: 24px;
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
.check-item.pending { background: rgba(255, 255, 255, 0.05); color: rgba(255, 255, 255, 0.5); }

.check-icon { font-weight: bold; }

.setup-warning {
  margin-bottom: 20px;
  padding: 12px;
  background: rgba(230, 162, 60, 0.1);
  border: 1px solid rgba(230, 162, 60, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: #e6a23c;
}

.setup-warning p { margin: 0 0 8px; }

.docker-link {
  color: #79bbff;
  text-decoration: none;
  font-size: 12px;
}

.docker-link:hover { text-decoration: underline; }

.setup-form {
  text-align: left;
}

.form-group {
  margin-bottom: 16px;
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

.form-input:focus {
  border-color: #409eff;
}

.form-input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.form-hint {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 4px;
}

.setup-btn {
  width: 100%;
  padding: 12px;
  margin-top: 8px;
  background: #409eff;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.setup-btn:hover:not(:disabled) { background: #66b1ff; }

.setup-btn:disabled {
  background: rgba(64, 158, 255, 0.4);
  cursor: not-allowed;
}

.setup-message {
  margin-top: 12px;
  font-size: 13px;
  text-align: center;
}

.setup-message.ok { color: #67c23a; }
.setup-message.error { color: #f56c6c; }
</style>
