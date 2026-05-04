<template>
  <div class="setup-container">
    <div class="setup-card">
      <div class="setup-header">
        <h1>Safe-CLI-Agent</h1>
        <p>配置 Docker 执行环境</p>
      </div>

      <div class="setup-body">
        <div class="form-section">
          <h3>镜像选择</h3>
          <div class="preset-grid">
            <div
              v-for="preset in presets"
              :key="preset.image"
              class="preset-card"
              :class="{ active: config.image === preset.image }"
              @click="selectPreset(preset)"
            >
              <div class="preset-name">{{ preset.name }}</div>
              <div class="preset-image">{{ preset.image }}</div>
              <div class="preset-desc">{{ preset.description }}</div>
            </div>
          </div>
          <div class="form-group">
            <label>自定义镜像</label>
            <input v-model="config.image" type="text" placeholder="alpine:latest" />
          </div>
        </div>

        <div class="form-section">
          <h3>容器配置</h3>
          <div class="form-row">
            <div class="form-group">
              <label>容器名称</label>
              <input v-model="config.container_name" type="text" placeholder="cli_agent_sandbox" />
            </div>
            <div class="form-group">
              <label>网络模式</label>
              <select v-model="config.network">
                <option value="none">无网络 (none)</option>
                <option value="bridge">桥接 (bridge)</option>
                <option value="host">主机 (host)</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>内存限制</label>
              <select v-model="config.memory_limit">
                <option value="256m">256 MB</option>
                <option value="512m">512 MB</option>
                <option value="1g">1 GB</option>
                <option value="2g">2 GB</option>
                <option value="4g">4 GB</option>
              </select>
            </div>
            <div class="form-group">
              <label>命令超时 (秒)</label>
              <input v-model.number="config.timeout" type="number" min="5" max="300" />
            </div>
          </div>
        </div>

        <div class="form-section">
          <h3>存储配置</h3>
          <div class="form-row">
            <div class="form-group">
              <label class="checkbox-label">
                <input v-model="config.use_host_workspace" type="checkbox" />
                <span>挂载宿主机工作目录</span>
              </label>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input v-model="config.use_knowledge_base" type="checkbox" />
                <span>挂载知识库目录</span>
              </label>
            </div>
          </div>
          <div class="form-group" v-if="config.use_knowledge_base">
            <label>知识库权限</label>
            <select v-model="config.kb_mode">
              <option value="ro">只读 (ro)</option>
              <option value="rw">读写 (rw)</option>
            </select>
          </div>
        </div>
      </div>

      <div class="setup-footer">
        <button class="btn btn-primary" @click="submitConfig" :disabled="submitting">
          {{ submitting ? '配置中...' : '开始使用' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDockerConfig, updateDockerConfig } from '@/api/config'
import type { DockerPreset, DockerConfigForm } from '@/types'

const router = useRouter()
const presets = ref<DockerPreset[]>([])
const submitting = ref(false)

const config = reactive<DockerConfigForm>({
  image: 'alpine:latest',
  container_name: 'cli_agent_sandbox',
  network: 'none',
  memory_limit: '512m',
  timeout: 30,
  use_host_workspace: false,
  use_knowledge_base: true,
  kb_mode: 'ro',
})

const selectPreset = (preset: DockerPreset) => {
  config.image = preset.image
}

const submitConfig = async () => {
  submitting.value = true
  try {
    await updateDockerConfig(config)
    router.push('/')
  } catch (e) {
    alert('配置失败: ' + (e instanceof Error ? e.message : '未知错误'))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const data = await getDockerConfig()
    presets.value = data.presets
    Object.assign(config, data.current)
  } catch {
    // 使用默认值
  }
})
</script>

<style lang="scss">
.setup-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  padding: 24px;
}

.setup-card {
  width: 100%;
  max-width: 640px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  overflow: hidden;
}

.setup-header {
  text-align: center;
  padding: 32px 24px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  h1 {
    color: #fff;
    font-size: 24px;
    font-weight: 700;
    margin: 0 0 8px;
  }

  p {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
    margin: 0;
  }
}

.setup-body {
  padding: 24px;
  max-height: 60vh;
  overflow-y: auto;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 3px; }
}

.form-section {
  margin-bottom: 24px;

  &:last-child { margin-bottom: 0; }

  h3 {
    color: #fff;
    font-size: 15px;
    font-weight: 600;
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.preset-card {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover { border-color: rgba(255, 255, 255, 0.3); }

  &.active {
    border-color: #007bff;
    background: rgba(0, 123, 255, 0.1);
  }

  .preset-name {
    color: #fff;
    font-size: 14px;
    font-weight: 600;
  }

  .preset-image {
    color: rgba(255, 255, 255, 0.5);
    font-size: 11px;
    font-family: 'Fira Code', monospace;
    margin-top: 2px;
  }

  .preset-desc {
    color: rgba(255, 255, 255, 0.5);
    font-size: 12px;
    margin-top: 4px;
  }
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-group {
  margin-bottom: 14px;

  label {
    display: block;
    color: rgba(255, 255, 255, 0.7);
    font-size: 13px;
    margin-bottom: 6px;
  }

  input[type="text"],
  input[type="number"],
  select {
    width: 100%;
    padding: 9px 12px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    color: #fff;
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s;

    &:focus { border-color: #007bff; }
    &::placeholder { color: rgba(255, 255, 255, 0.3); }
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding-top: 8px;

    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      cursor: pointer;
      accent-color: #007bff;
    }

    span {
      color: #fff;
      font-size: 13px;
    }
  }
}

.setup-footer {
  padding: 20px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;

  .btn {
    width: 100%;
    padding: 12px;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;

    &.btn-primary {
      background: #007bff;
      color: #fff;

      &:hover:not(:disabled) { background: #0069d9; }
      &:disabled { opacity: 0.5; cursor: not-allowed; }
    }
  }
}
</style>
