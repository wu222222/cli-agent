<template>
  <div class="settings-container">
    <div class="settings-header">
      <h2>设置</h2>
    </div>

    <div class="settings-content">
      <div class="settings-section">
        <h3>API 配置</h3>
        <div class="form-group">
          <label>API 地址</label>
          <input
            v-model="settings.apiUrl"
            type="text"
            placeholder="http://localhost:8000"
          />
        </div>
        <div class="form-group">
          <label>API 密钥</label>
          <input
            v-model="settings.apiKey"
            type="password"
            placeholder="输入 API 密钥"
          />
        </div>
      </div>

      <div class="settings-section">
        <h3>安全设置</h3>
        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="settings.requireConfirmation"
              type="checkbox"
            />
            <span>命令执行前需要确认</span>
          </label>
        </div>
        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="settings.enableNetwork"
              type="checkbox"
            />
            <span>允许容器访问网络</span>
          </label>
        </div>
      </div>

      <div class="settings-section">
        <h3>显示设置</h3>
        <div class="form-group">
          <label>主题</label>
          <select v-model="settings.theme">
            <option value="dark">深色</option>
            <option value="light">浅色</option>
          </select>
        </div>
        <div class="form-group">
          <label>字体大小</label>
          <input
            v-model.number="settings.fontSize"
            type="range"
            min="12"
            max="18"
          />
          <span>{{ settings.fontSize }}px</span>
        </div>
      </div>

      <div class="settings-actions">
        <button class="btn btn-primary" @click="saveSettings">保存设置</button>
        <button class="btn btn-secondary" @click="resetSettings">重置默认</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

interface Settings {
  apiUrl: string
  apiKey: string
  requireConfirmation: boolean
  enableNetwork: boolean
  theme: string
  fontSize: number
}

const settings = reactive<Settings>({
  apiUrl: 'http://localhost:8000',
  apiKey: '',
  requireConfirmation: true,
  enableNetwork: false,
  theme: 'dark',
  fontSize: 14
})

const saveSettings = () => {
  console.log('Settings saved:', settings)
}

const resetSettings = () => {
  settings.apiUrl = 'http://localhost:8000'
  settings.apiKey = ''
  settings.requireConfirmation = true
  settings.enableNetwork = false
  settings.theme = 'dark'
  settings.fontSize = 14
}
</script>

<style lang="scss">
.settings-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.settings-header {
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  h2 {
    color: #fff;
    font-size: 18px;
    font-weight: 600;
    margin: 0;
  }
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
  }
}

.settings-section {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;

  h3 {
    color: #fff;
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
}

.form-group {
  margin-bottom: 16px;

  &:last-child {
    margin-bottom: 0;
  }

  label {
    display: block;
    color: rgba(255, 255, 255, 0.7);
    font-size: 13px;
    margin-bottom: 8px;
  }

  input[type="text"],
  input[type="password"],
  select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    color: #fff;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;

    &:focus {
      border-color: #007bff;
    }

    &::placeholder {
      color: rgba(255, 255, 255, 0.4);
    }
  }

  input[type="range"] {
    width: calc(100% - 60px);
    vertical-align: middle;
    margin-right: 12px;
  }

  span {
    color: rgba(255, 255, 255, 0.7);
    font-size: 14px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;

    input[type="checkbox"] {
      width: 18px;
      height: 18px;
      cursor: pointer;
    }

    span {
      color: #fff;
      font-size: 14px;
    }
  }
}

.settings-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding-top: 16px;

  .btn {
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;

    &.btn-primary {
      background: #007bff;
      color: #fff;

      &:hover {
        background: #0069d9;
      }
    }

    &.btn-secondary {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;

      &:hover {
        background: rgba(255, 255, 255, 0.2);
      }
    }
  }
}
</style>