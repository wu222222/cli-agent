<template>
  <div class="tools-tab">
    <div class="tools-header">
      <span class="tools-title">工具</span>
      <router-link to="/tools" class="tools-expand-link" @click="$emit('navigate')">详细设置 →</router-link>
    </div>
    <div class="tools-list">
      <div
        v-for="tool in availableTools"
        :key="tool.name"
        class="tool-item"
        :class="{ selected: selectedTools.includes(tool.name) }"
        @click="toggleTool(tool.name)"
      >
        <span class="tool-check">{{ selectedTools.includes(tool.name) ? '✅' : '☐' }}</span>
        <span class="tool-name">{{ tool.name }}</span>
        <span class="tool-badge" :class="tool.plugin_type">{{ tool.plugin_type }}</span>
      </div>
      <div v-if="availableTools.length === 0" class="tools-empty">
        暂无可用工具
      </div>
    </div>
    <div class="tools-footer">
      <button class="tools-save-btn" @click="saveTools" :disabled="!hasChanges">
        {{ saving ? '保存中...' : '保存' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import api from '@/api/agent'
import { updateSessionToolNames } from '@/api/config'
import { useChatStore } from '@/stores/chat'
import { useToast } from '@/composables/useToast'

defineEmits<{
  (e: 'navigate'): void
}>()

const chatStore = useChatStore()
const toast = useToast()
const availableTools = ref<any[]>([])
const selectedTools = ref<string[]>([])
const savedTools = ref<string[]>([])
const saving = ref(false)

const hasChanges = computed(() => {
  return JSON.stringify([...selectedTools.value].sort()) !== JSON.stringify([...savedTools.value].sort())
})

function toggleTool(name: string) {
  const idx = selectedTools.value.indexOf(name)
  if (idx >= 0) {
    selectedTools.value.splice(idx, 1)
  } else {
    selectedTools.value.push(name)
  }
}

async function loadTools() {
  try {
    const resp = await api.get('/agent/tools')
    const tools = resp.data.available_tools || []
    availableTools.value = tools.filter((t: any) => t.plugin_type !== 'command')
    selectedTools.value = resp.data.tool_names || []
    savedTools.value = [...selectedTools.value]
  } catch { /* ignore */ }
}

async function saveTools() {
  saving.value = true
  try {
    await api.post('/agent/tools', { tool_names: selectedTools.value })
    if (chatStore.currentSessionId) {
      await updateSessionToolNames(chatStore.currentSessionId, selectedTools.value)
    }
    savedTools.value = [...selectedTools.value]
    chatStore.toolsUpdatedAt = Date.now()
    toast.success('工具配置已保存')
  } catch (e) {
    console.error('保存工具配置失败:', e)
    toast.error('保存工具配置失败')
  } finally {
    saving.value = false
  }
}

// 切换会话时重新加载
watch(() => chatStore.currentSessionId, () => {
  loadTools()
})

onMounted(loadTools)
</script>

<style scoped>
.tools-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tools-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #2d2e3a;
}

.tools-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
}

.tools-expand-link {
  font-size: 11px;
  color: #79bbff;
  text-decoration: none;
  transition: color 0.15s;
}

.tools-expand-link:hover {
  color: #a0cfff;
}

.tools-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
}

.tool-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.tool-item.selected {
  background: rgba(64, 158, 255, 0.08);
}

.tool-check {
  font-size: 13px;
  width: 18px;
  text-align: center;
}

.tool-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  flex: 1;
}

.tool-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: uppercase;
}

.tool-badge.exec { background: rgba(0, 123, 255, 0.2); color: #6cb2ff; }
.tool-badge.local { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
.tool-badge.network { background: rgba(40, 167, 69, 0.2); color: #7bdd8a; }

.tools-empty {
  text-align: center;
  color: #666;
  font-size: 12px;
  padding: 20px 0;
}

.tools-footer {
  padding: 8px 12px;
  border-top: 1px solid #2d2e3a;
}

.tools-save-btn {
  width: 100%;
  padding: 6px 0;
  background: #409eff;
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.tools-save-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.tools-save-btn:disabled {
  background: rgba(64, 158, 255, 0.3);
  cursor: not-allowed;
}
</style>
