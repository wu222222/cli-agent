<template>
  <div class="plugin-panel">
    <div class="panel-header">
      <h3>插件管理</h3>
      <el-button size="small" circle @click="pluginStore.fetchPlugins()">&#x21bb;</el-button>
    </div>

    <div class="panel-filters">
      <el-radio-group v-model="pluginStore.activeFilter" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="local">本地</el-radio-button>
        <el-radio-button value="exec">容器执行</el-radio-button>
        <el-radio-button value="network">网络服务</el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="pluginStore.plugins.length === 0" class="empty-hint">
      暂无插件
    </div>

    <el-collapse v-else>
      <el-collapse-item v-for="plugin in pluginStore.filteredPlugins" :key="plugin.name">
        <template #title>
          <div class="plugin-header">
            <span class="plugin-name">{{ plugin.name }}</span>
            <el-tag :type="getTypeTag(plugin.tool_type)" size="small">
              {{ getTypeLabel(plugin.tool_type) }}
            </el-tag>
            <el-tag :type="plugin.status === 'running' ? 'success' : 'info'" size="small">
              {{ plugin.status === 'running' ? '运行中' : '已停止' }}
            </el-tag>
          </div>
        </template>

        <div class="plugin-details">
          <p class="plugin-desc">{{ plugin.description }}</p>

          <div class="plugin-meta">
            <el-tag v-if="plugin.bound_action" size="small" type="info">
              动作: {{ plugin.bound_action }}
            </el-tag>
            <el-tag v-if="plugin.param_mode" size="small" type="info">
              参数模式: {{ plugin.param_mode }}
            </el-tag>
            <el-tag v-if="plugin.requires_confirmation" size="small" type="warning">
              需确认
            </el-tag>
          </div>

          <div v-if="plugin.image" class="plugin-image">
            <span class="meta-label">镜像:</span> <code>{{ plugin.image }}</code>
          </div>

          <div v-if="plugin.parameters && Object.keys(plugin.parameters).length > 0" class="plugin-params">
            <div class="params-title">参数：</div>
            <div v-for="(param, key) in plugin.parameters" :key="String(key)" class="param-item">
              <code>{{ key }}</code>
              <span class="param-type">({{ param.type }})</span>
              <span class="param-desc">{{ param.description }}</span>
              <el-tag v-if="plugin.required_params?.includes(String(key))" size="small" type="danger">必填</el-tag>
            </div>
          </div>

          <div class="plugin-actions">
            <el-button
              size="small"
              :type="plugin.status === 'running' ? 'danger' : 'success'"
              :loading="!!pluginStore.loading[plugin.name]"
              @click.stop="pluginStore.togglePlugin(plugin.name)"
            >
              {{ plugin.status === 'running' ? '停止' : '启动' }}
            </el-button>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { usePluginStore } from '@/stores/plugin'

const pluginStore = usePluginStore()

onMounted(() => {
  pluginStore.fetchPlugins()
})

function getTypeTag(type: string) {
  const map: Record<string, string> = { exec: 'warning', network: 'success', local: 'info' }
  return (map[type] || 'info') as 'warning' | 'success' | 'info'
}

function getTypeLabel(type: string) {
  const map: Record<string, string> = { exec: '容器执行', network: '网络服务', local: '本地' }
  return map[type] || type
}
</script>

<style scoped lang="scss">
.plugin-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;

  h3 {
    margin: 0;
    font-size: 16px;
    color: #e0e0e0;
  }
}

.panel-filters {
  padding: 0 4px;
}

.empty-hint {
  text-align: center;
  color: #888;
  padding: 20px 0;
}

.plugin-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.plugin-name {
  font-weight: 600;
}

.plugin-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plugin-desc {
  color: #aaa;
  margin: 0;
  font-size: 13px;
}

.plugin-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.plugin-image {
  font-size: 13px;
  color: #ccc;

  .meta-label {
    color: #888;
  }

  code {
    background: rgba(255, 255, 255, 0.06);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
  }
}

.plugin-params {
  .params-title {
    font-size: 13px;
    color: #aaa;
    margin-bottom: 4px;
  }

  .param-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 0;
    font-size: 12px;

    code {
      background: rgba(255, 255, 255, 0.06);
      padding: 1px 5px;
      border-radius: 3px;
    }

    .param-type {
      color: #666;
    }

    .param-desc {
      color: #aaa;
    }
  }
}

.plugin-actions {
  display: flex;
  gap: 8px;
}
</style>
