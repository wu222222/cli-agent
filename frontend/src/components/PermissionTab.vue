<template>
  <div class="permission-tab">
    <div class="perm-header">
      <span class="perm-title">权限白名单</span>
      <button
        v-if="permissions.length > 0"
        class="perm-clear-btn"
        @click="clearAll"
        :disabled="clearing"
      >
        {{ clearing ? '清空中...' : '清空全部' }}
      </button>
    </div>

    <div class="perm-list">
      <div v-if="permissions.length === 0" class="perm-empty">
        暂无白名单规则
        <br><small>在确认框中点击"一直执行"添加</small>
      </div>

      <div v-for="perm in permissions" :key="perm.id" class="perm-item">
        <div class="perm-item-header">
          <span class="perm-tool">{{ perm.tool }}</span>
          <button class="perm-delete" @click="deleteRule(perm.id)" title="删除">×</button>
        </div>
        <div class="perm-pattern">{{ perm.command_pattern }}</div>
        <div v-if="perm.description" class="perm-desc">{{ perm.description }}</div>
        <div class="perm-time">{{ formatTime(perm.created_at) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import api from '@/api/agent'
import { useChatStore } from '@/stores/chat'
import { useToast } from '@/composables/useToast'

interface PermissionRule {
  id: string
  tool: string
  command_pattern: string
  description: string
  created_at: string
}

const chatStore = useChatStore()
const toast = useToast()
const permissions = ref<PermissionRule[]>([])
const clearing = ref(false)

async function loadPermissions() {
  if (!chatStore.currentSessionId) {
    permissions.value = []
    return
  }
  try {
    const resp = await api.get('/agent/permissions', {
      params: { session_id: chatStore.currentSessionId }
    })
    permissions.value = resp.data.permissions || []
  } catch {
    permissions.value = []
  }
}

async function deleteRule(ruleId: string) {
  if (!chatStore.currentSessionId) return
  try {
    await api.delete(`/agent/permissions/${ruleId}`, {
      params: { session_id: chatStore.currentSessionId }
    })
    permissions.value = permissions.value.filter(p => p.id !== ruleId)
    toast.success('已删除规则')
  } catch (e: any) {
    toast.error('删除失败: ' + e.message)
  }
}

async function clearAll() {
  if (!chatStore.currentSessionId) return
  clearing.value = true
  try {
    await api.delete('/agent/permissions', {
      params: { session_id: chatStore.currentSessionId }
    })
    permissions.value = []
    toast.success('已清空白名单')
  } catch (e: any) {
    toast.error('清空失败: ' + e.message)
  } finally {
    clearing.value = false
  }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

// 切换会话时重新加载
watch(() => chatStore.currentSessionId, () => {
  loadPermissions()
})

onMounted(loadPermissions)

// 暴露刷新方法
defineExpose({ loadPermissions })
</script>

<style scoped>
.permission-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.perm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #2d2e3a;
}

.perm-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
}

.perm-clear-btn {
  padding: 4px 10px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 4px;
  color: #f08080;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.perm-clear-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
}

.perm-clear-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.perm-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.perm-empty {
  text-align: center;
  color: #666;
  font-size: 12px;
  padding: 30px 0;
}

.perm-empty small {
  display: block;
  margin-top: 8px;
  color: #555;
  font-size: 11px;
}

.perm-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.perm-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.perm-tool {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(64, 158, 255, 0.15);
  color: #79bbff;
  border-radius: 3px;
  font-family: monospace;
}

.perm-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  border-radius: 4px;
  font-size: 16px;
  transition: all 0.15s;
}

.perm-delete:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #f08080;
}

.perm-pattern {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  font-family: monospace;
  margin-top: 6px;
  word-break: break-all;
}

.perm-desc {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
}

.perm-time {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.25);
  margin-top: 4px;
}

.perm-list::-webkit-scrollbar { width: 4px; }
.perm-list::-webkit-scrollbar-track { background: transparent; }
.perm-list::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 2px; }
</style>
