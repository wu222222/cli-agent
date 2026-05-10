<template>
  <div class="setup-container">
    <header class="setup-header">
      <h1>Docker 配置</h1>
      <button class="back-button" @click="goToChat">← 返回对话</button>
    </header>

    <div class="setup-content">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else class="config-section">
        <div class="preset-section">
          <h3>快速预设</h3>
          <div class="preset-list">
            <button
              v-for="preset in presets"
              :key="preset.name"
              class="preset-button"
              :class="{ active: selectedPreset === preset.name }"
              @click="applyPreset(preset)"
            >
              <span class="preset-name">{{ preset.name }}</span>
              <span class="preset-desc">{{ preset.description }}</span>
            </button>
          </div>
        </div>

        <div class="form-section">
          <div class="form-group">
            <label>Docker 镜像</label>
            <input v-model="form.image" placeholder="alpine:latest" />
          </div>

          <div class="form-group">
            <label>容器名称</label>
            <input v-model="form.container_name" placeholder="cli_agent_sandbox" />
          </div>

          <div class="form-group">
            <label>网络模式</label>
            <select v-model="form.network">
              <option value="none">无网络</option>
              <option value="bridge">桥接网络</option>
              <option value="host">主机网络</option>
            </select>
          </div>

          <div class="form-group">
            <label>内存限制</label>
            <input v-model="form.memory_limit" placeholder="512m" />
          </div>

          <div class="form-group">
            <label>超时时间 (秒)</label>
            <input v-model.number="form.timeout" type="number" min="1" max="300" />
          </div>

          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" v-model="form.use_host_workspace" />
              挂载宿主机工作目录
            </label>
          </div>

          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" v-model="form.use_knowledge_base" />
              启用知识库
            </label>
          </div>

          <div class="form-group" v-if="form.use_knowledge_base">
            <label>知识库模式</label>
            <select v-model="form.kb_mode">
              <option value="ro">只读</option>
              <option value="rw">读写</option>
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="save-button" @click="saveConfig" :disabled="saving">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
          <span v-if="saveSuccess" class="success-hint">✓ 已保存</span>
          <span v-if="saveError" class="error-hint">{{ saveError }}</span>
        </div>
      </div>

      <div class="plugin-section">
        <h3>插件管理</h3>
        <PluginPanel />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDockerConfig, updateDockerConfig } from '@/api/config'
import type { DockerPreset, DockerConfigForm } from '@/types'
import PluginPanel from '@/components/PluginPanel.vue'

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const saveSuccess = ref(false)
const saveError = ref('')
const selectedPreset = ref('')
const presets = ref<DockerPreset[]>([])

const form = ref<DockerConfigForm>({
  image: 'alpine:latest',
  container_name: 'cli_agent_sandbox',
  network: 'none',
  memory_limit: '512m',
  timeout: 30,
  use_host_workspace: false,
  use_knowledge_base: true,
  kb_mode: 'ro'
})

function goToChat() {
  router.push('/')
}

function applyPreset(preset: DockerPreset) {
  selectedPreset.value = preset.name
  form.value.image = preset.image
}

async function loadConfig() {
  try {
    const data = await getDockerConfig()
    presets.value = data.presets
    if (data.current) {
      form.value = { ...form.value, ...data.current }
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = ''

  try {
    await updateDockerConfig(form.value)
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 2000)
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '保存失败'
    saveError.value = errMsg
    setTimeout(() => { saveError.value = '' }, 3000)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.setup-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: rgba(255, 255, 255, 0.9);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  padding: 20px;
}

.setup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.setup-header h1 {
  margin: 0;
  font-size: 24px;
}

.back-button {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: inherit;
  cursor: pointer;
  transition: background 0.2s;
}

.back-button:hover {
  background: rgba(255, 255, 255, 0.2);
}

.setup-content {
  max-width: 600px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: rgba(255, 255, 255, 0.5);
}

.config-section,
.plugin-section {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.config-section h3,
.plugin-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
}

.preset-section {
  margin-bottom: 24px;
}

.preset-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preset-button {
  display: flex;
  flex-direction: column;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: inherit;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.preset-button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.preset-button.active {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.1);
}

.preset-name {
  font-weight: 500;
  font-size: 14px;
}

.preset-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.form-group input,
.form-group select {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: inherit;
  font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-group input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.save-button {
  padding: 10px 24px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.save-button:hover:not(:disabled) {
  background: #66b1ff;
}

.save-button:disabled {
  background: rgba(64, 158, 255, 0.5);
  cursor: not-allowed;
}

.success-hint {
  color: #67c23a;
  font-size: 13px;
}

.error-hint {
  color: #f56c6c;
  font-size: 13px;
}
</style>
