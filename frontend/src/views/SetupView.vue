<template>
  <div class="setup-container">
    <!-- 标题栏 -->
    <TitleBar>
      <template #right>
        <button v-if="isStandalone" class="title-icon-btn" @click="exitApp" title="退出应用">
          <svg width="14" height="14" viewBox="0 0 12 12"><path d="M2 2L10 10M10 2L2 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
        <button v-else class="title-icon-btn" @click="skipSetup" title="返回">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        </button>
      </template>
    </TitleBar>

    <div class="setup-card">
      <div class="setup-header">
        <div class="setup-logo">🛡</div>
        <h1 class="setup-title">Safe-CLI-Agent</h1>
      </div>

      <!-- Tab 切换 -->
      <div class="setup-tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'api' }"
          @click="activeTab = 'api'"
        >API 配置</button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'plugins' }"
          @click="activeTab = 'plugins'; loadPluginConfig()"
        >插件配置</button>
      </div>

      <!-- API 配置 Tab -->
      <div v-show="activeTab === 'api'" class="tab-content">
        <!-- 环境检测 -->
        <div class="setup-checks">
          <div class="check-item" :class="loading ? 'pending' : dockerClass">
            <span class="check-icon">{{ loading ? '…' : dockerIcon }}</span>
            <span>{{ loading ? '检测中...' : dockerLabel }}</span>
          </div>
          <div class="check-item" :class="loading ? 'pending' : (status.has_env ? 'ok' : 'fail')">
            <span class="check-icon">{{ loading ? '…' : (status.has_env ? '✓' : '✕') }}</span>
            <span>{{ loading ? '检测中...' : `.env ${status.has_env ? '已创建' : '未创建'}` }}</span>
          </div>
          <div class="check-item" :class="loading ? 'pending' : (status.configured ? 'ok' : 'pending')">
            <span class="check-icon">{{ loading ? '…' : (status.configured ? '✓' : '○') }}</span>
            <span>{{ loading ? '检测中...' : `API ${status.configured ? '已配置' : '待配置'}` }}</span>
          </div>
        </div>

        <!-- 配置表单 -->
        <div class="setup-form">
          <!-- Docker 提示 -->
          <div v-if="!loading && status.docker_status === 'not_installed'" class="setup-warning">
            <p>Docker 未安装。容器插件功能需要 Docker 支持。</p>
            <a href="https://www.docker.com/products/docker-desktop/" target="_blank" class="docker-link">
              下载 Docker Desktop →
            </a>
          </div>
          <div v-else-if="!loading && status.docker_status === 'not_running'" class="setup-warning warn-yellow">
            <p>Docker 已安装但未启动。请打开 Docker Desktop 启动服务。</p>
          </div>

          <!-- 环境变量来源提示 -->
          <div v-if="!loading && status.config_source === 'env'" class="setup-info">
            <p>检测到系统环境变量已配置，无需重复填写。</p>
          </div>
          <div v-else-if="!loading && status.config_source === 'partial'" class="setup-warning warn-yellow">
            <p>检测到部分配置，请补全以下必填项。</p>
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input
              v-model="form.api_key"
              type="password"
              :placeholder="status.api_key || 'sk-xxxxxxxxxx'"
              class="form-input"
            />
            <span class="form-hint">
              <template v-if="status.config_source === 'env'">已从系统环境变量读取（留空则保留）</template>
              <template v-else>兼容 OpenAI 格式的 API Key（可选，留空则使用环境变量）</template>
            </span>
          </div>

          <div class="form-group">
            <label>Base URL <span class="required">*</span></label>
            <input
              v-model="form.base_url"
              type="text"
              :placeholder="status.base_url || 'https://api.openai.com/v1'"
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

          <button class="setup-btn" @click="saveConfig" :disabled="saving">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>

          <p v-if="apiMessage" class="setup-message" :class="apiMessageType">{{ apiMessage }}</p>

          <button class="skip-btn" @click="skipSetup">
            {{ status.configured ? '进入主界面' : '跳过，直接进入' }}
          </button>
        </div>
      </div>

      <!-- 插件配置 Tab -->
      <div v-show="activeTab === 'plugins'" class="tab-content">
        <div class="yaml-editor-area">
          <div class="yaml-toolbar">
            <span class="yaml-filename">config/plugins.yaml</span>
            <div class="yaml-actions">
              <span v-if="yamlValid === true" class="yaml-status ok">✓ 格式正确</span>
              <span v-else-if="yamlValid === false" class="yaml-status error">✕ 格式错误</span>
              <button class="yaml-btn" @click="loadPluginConfig" :disabled="yamlLoading">重新加载</button>
              <button class="yaml-btn primary" @click="savePluginConfig" :disabled="yamlSaving || yamlValid === false">
                {{ yamlSaving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
          <textarea
            v-model="yamlContent"
            class="yaml-textarea"
            spellcheck="false"
            @input="validateYaml"
            placeholder="# 在此编辑 plugins.yaml..."
          ></textarea>
          <p v-if="yamlMessage" class="setup-message" :class="yamlMessageType">{{ yamlMessage }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { markConfigured } from '@/router'
import api from '@/api/agent'
import TitleBar from '@/components/TitleBar.vue'

const router = useRouter()
const activeTab = ref<'api' | 'plugins'>('api')
const loading = ref(true)
// 首次启动 = 未配置 = standalone（显示关闭按钮）；已配置 = 从设置进入（显示返回按钮）
const isStandalone = ref(true)

// === API 配置 ===
const saving = ref(false)
const apiMessage = ref('')
const apiMessageType = ref<'ok' | 'error'>('ok')

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
    form.value.base_url = resp.data.base_url || ''
    form.value.model = resp.data.model || ''
    // 已配置 = 从设置按钮进入，非首次启动
    isStandalone.value = !resp.data.configured
  } catch {} finally {
    loading.value = false
  }
})

async function saveConfig() {
  saving.value = true
  apiMessage.value = ''
  try {
    const resp = await api.post('/setup/save', form.value)
    if (resp.data.success) {
      apiMessageType.value = 'ok'
      apiMessage.value = resp.data.message
      status.value.configured = true
      markConfigured()
    } else {
      apiMessageType.value = 'error'
      apiMessage.value = resp.data.message
    }
  } catch (e: any) {
    apiMessageType.value = 'error'
    apiMessage.value = '保存失败: ' + (e.message || '未知错误')
  } finally {
    saving.value = false
  }
}

function skipSetup() {
  markConfigured()
  router.replace('/')
}

function exitApp() {
  window.electronAPI?.quitApp()
}

// === 插件配置 ===
const yamlContent = ref('')
const yamlValid = ref<boolean | null>(null)
const yamlLoading = ref(false)
const yamlSaving = ref(false)
const yamlMessage = ref('')
const yamlMessageType = ref<'ok' | 'error'>('ok')

async function loadPluginConfig() {
  yamlLoading.value = true
  yamlMessage.value = ''
  try {
    const resp = await api.get('/plugins/config')
    yamlContent.value = resp.data.content || ''
    validateYaml()
  } catch (e: any) {
    yamlMessage.value = '加载失败: ' + e.message
    yamlMessageType.value = 'error'
  } finally {
    yamlLoading.value = false
  }
}

function validateYaml() {
  const content = yamlContent.value.trim()
  if (!content) {
    yamlValid.value = null
    return
  }
  // 简单验证：检查基本结构
  try {
    // 浏览器端没有 js-yaml，做基础检查
    if (content.includes('plugins:') && !content.match(/^\s*#/m)?.length) {
      yamlValid.value = true
    } else if (content.match(/^\s*#/m)) {
      // 有注释行也算有效（YAML 合法）
      yamlValid.value = content.includes('plugins:')
    } else {
      yamlValid.value = false
    }
  } catch {
    yamlValid.value = false
  }
}

async function savePluginConfig() {
  yamlSaving.value = true
  yamlMessage.value = ''
  try {
    const resp = await api.post('/plugins/config', { content: yamlContent.value })
    if (resp.data.success) {
      yamlMessageType.value = 'ok'
      yamlMessage.value = resp.data.message
    } else {
      yamlMessageType.value = 'error'
      yamlMessage.value = resp.data.message
    }
  } catch (e: any) {
    yamlMessageType.value = 'error'
    yamlMessage.value = '保存失败: ' + (e.message || '未知错误')
  } finally {
    yamlSaving.value = false
  }
}
</script>

<style scoped>
.setup-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* 标题栏图标按钮 */
.title-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s;
}

.title-icon-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.9);
}

.setup-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 40px;
  overflow-y: auto;
}

.setup-card-wide {
  width: 100%;
  max-width: 720px;
}

.setup-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 16px;
}

.setup-logo {
  font-size: 28px;
}

.setup-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

/* Tab 栏 */
.setup-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 20px;
}

.tab-btn {
  flex: 1;
  padding: 10px 32px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: rgba(255, 255, 255, 0.45);
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: rgba(255, 255, 255, 0.7);
}

.tab-btn.active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.tab-content {
  text-align: left;
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* 环境检测 */
.setup-checks {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
  text-align: center;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 8px;
}

.check-item.ok { background: rgba(103, 194, 58, 0.1); color: #67c23a; }
.check-item.fail { background: rgba(245, 108, 108, 0.1); color: #f56c6c; }
.check-item.warn { background: rgba(230, 162, 60, 0.1); color: #e6a23c; }
.check-item.pending { background: rgba(255, 255, 255, 0.05); color: rgba(255, 255, 255, 0.5); }

.check-icon { font-weight: bold; }

.setup-warning {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.2);
  border-radius: 8px;
  font-size: 12px;
  color: #f56c6c;
}

.setup-warning.warn-yellow {
  background: rgba(230, 162, 60, 0.1);
  border-color: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.setup-warning p { margin: 0 0 4px; }

.docker-link {
  color: #79bbff;
  text-decoration: none;
  font-size: 12px;
}

.docker-link:hover { text-decoration: underline; }

.setup-info {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(103, 194, 58, 0.08);
  border: 1px solid rgba(103, 194, 58, 0.15);
  border-radius: 8px;
  font-size: 12px;
  color: #67c23a;
}

.setup-info p { margin: 0; }

.setup-form {
  text-align: left;
  max-width: 440px;
  width: 100%;
  margin: 0 auto;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 5px;
}

.required { color: #f56c6c; }

.form-input {
  width: 100%;
  padding: 9px 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
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
  margin-top: 3px;
}

.setup-btn {
  width: 100%;
  padding: 10px;
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
  margin-top: 8px;
  font-size: 12px;
  text-align: center;
}

.setup-message.ok { color: #67c23a; }
.setup-message.error { color: #f56c6c; }

.skip-btn {
  width: 100%;
  padding: 9px;
  margin-top: 12px;
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

/* YAML 编辑器 */
.yaml-editor-area {
  display: flex;
  flex-direction: column;
  flex: 1;
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
}

.yaml-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.yaml-filename {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  font-family: 'Fira Code', monospace;
}

.yaml-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.yaml-status {
  font-size: 11px;
}

.yaml-status.ok { color: #67c23a; }
.yaml-status.error { color: #f56c6c; }

.yaml-btn {
  padding: 5px 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.yaml-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.yaml-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.yaml-btn.primary {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}

.yaml-btn.primary:hover:not(:disabled) {
  background: #66b1ff;
}

.yaml-textarea {
  width: 100%;
  min-height: 480px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: #e0e0e0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
  tab-size: 2;
}

.yaml-textarea:focus {
  border-color: rgba(64, 158, 255, 0.4);
}

.yaml-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
}
</style>
