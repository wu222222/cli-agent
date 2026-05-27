<template>
  <div class="history-panel" :class="{ collapsed: isCollapsed }">
    <!-- 折叠态：只显示箭头 -->
    <div v-if="isCollapsed" class="collapsed-icon" @click="isCollapsed = false">
      <span title="展开历史对话">▶</span>
    </div>

    <!-- 展开态 -->
    <div v-else class="panel-content">
      <!-- 顶部：新建按钮 + 折叠按钮 -->
      <div class="panel-header">
        <button class="new-chat-btn" @click="handleNewChat">
          <span>＋</span> 新对话
        </button>
        <button class="collapse-btn" @click="isCollapsed = true" title="折叠">◀</button>
      </div>

      <!-- 对话列表 -->
      <div class="session-list">
        <div v-if="sessions.length === 0" class="empty-tip">
          暂无历史对话
        </div>
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="handleSelectSession(session.id)"
        >
          <div class="session-info">
            <div class="session-title">{{ session.title }}</div>
            <div class="session-meta">
              <span>{{ formatTime(session.updated_at) }}</span>
              <span>{{ session.message_count }} 条</span>
            </div>
            <div v-if="session.tool_names && session.tool_names.length > 0" class="session-tools">
              <span v-for="tool in session.tool_names.slice(0, 3)" :key="tool" class="tool-tag">
                {{ tool }}
              </span>
              <span v-if="session.tool_names.length > 3" class="tool-tag more">
                +{{ session.tool_names.length - 3 }}
              </span>
            </div>
          </div>
          <button
            class="delete-btn"
            @click.stop="confirmDelete(session.id, session.title)"
            title="删除对话"
          >
            ×
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认对话框 -->
    <div v-if="showDeleteConfirm" class="delete-confirm-overlay" @click="showDeleteConfirm = false">
      <div class="delete-confirm-dialog" @click.stop>
        <div class="delete-confirm-title">确认删除</div>
        <div class="delete-confirm-body">
          确定要删除对话「{{ deleteTarget.title }}」吗？
          <br><span class="delete-confirm-hint">此操作不可撤销</span>
        </div>
        <div class="delete-confirm-actions">
          <button class="delete-confirm-cancel" @click="showDeleteConfirm = false">取消</button>
          <button class="delete-confirm-ok" @click="handleDeleteSession">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SessionInfo } from '@/types'
import {
  listSessions,
  createSession,
  deleteSession as apiDeleteSession,
  resumeSession,
} from '@/api/config'
import { useChatStore, setLoadingSession } from '@/stores/chat'

const emit = defineEmits<{
  (e: 'new-chat'): void
  (e: 'resume-session', data: { session_id: string; messages: any[]; tool_names: string[] }): void
}>()

const chatStore = useChatStore()
const isCollapsed = ref(false)
const sessions = ref<SessionInfo[]>([])
const currentSessionId = ref<string | null>(null)
const showDeleteConfirm = ref(false)
const deleteTarget = ref<{ id: string; title: string }>({ id: '', title: '' })

// 加载会话列表
async function loadSessions() {
  try {
    sessions.value = await listSessions()
  } catch (e) {
    console.error('加载会话列表失败:', e)
  }
}

// 新建对话
async function handleNewChat() {
  try {
    const result = await createSession()
    currentSessionId.value = result.session_id
    chatStore.currentSessionId = result.session_id  // 同步到 chatStore
    chatStore.clearMessages()
    emit('new-chat')
    await loadSessions()
  } catch (e) {
    console.error('创建会话失败:', e)
  }
}

// 选择会话
async function handleSelectSession(sessionId: string) {
  if (currentSessionId.value === sessionId) return
  try {
    const data = await resumeSession(sessionId)
    currentSessionId.value = sessionId

    // 设置加载标志，防止 pushMessage 重复保存到 session
    setLoadingSession(true)

    // 直接替换整个消息数组（避免逐条 push 导致的渲染问题）
    const restoredMessages = data.messages.map((msg: any) => ({
      role: msg.role === 'user' ? 'user' as const : 'system' as const,
      content: msg.content,
      timestamp: msg.timestamp || new Date().toLocaleTimeString(),
      thought: msg.thought || '',
      type: msg.type || 'text' as const,
      agent: msg.agent || '',
      toolName: msg.toolName,
      command: msg.command,
    }))

    // 替换消息数组（Vue 响应式）
    chatStore.messages = restoredMessages

    // 恢复完成，关闭加载标志
    setLoadingSession(false)

    emit('resume-session', {
      session_id: sessionId,
      messages: data.messages,
      tool_names: data.tool_names,
    })
  } catch (e) {
    console.error('恢复会话失败:', e)
  }
}

// 显示删除确认
function confirmDelete(sessionId: string, title: string) {
  deleteTarget.value = { id: sessionId, title }
  showDeleteConfirm.value = true
}

// 删除会话
async function handleDeleteSession() {
  const sessionId = deleteTarget.value.id
  showDeleteConfirm.value = false
  try {
    await apiDeleteSession(sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      chatStore.clearMessages()
    }
    await loadSessions()
  } catch (e) {
    console.error('删除会话失败:', e)
  }
}

// 格式化时间
function formatTime(isoString: string): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return `${days}天前`
}

// 暴露给父组件的方法
defineExpose({
  loadSessions,
  setCurrentSessionId: (id: string | null) => { currentSessionId.value = id },
})

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.history-panel {
  width: 240px;
  background: #1a1b23;
  border-right: 1px solid #2d2e3a;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}

.history-panel.collapsed {
  width: 40px;
}

.collapsed-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  cursor: pointer;
  font-size: 18px;
  color: #8b8d9a;
}

.collapsed-icon:hover {
  color: #fff;
}

.panel-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px;
  border-bottom: 1px solid #2d2e3a;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #2d2e3a;
  border: none;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.new-chat-btn:hover {
  background: #3d3e4a;
}

.collapse-btn {
  background: none;
  border: none;
  color: #8b8d9a;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
}

.collapse-btn:hover {
  color: #fff;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.empty-tip {
  text-align: center;
  color: #666;
  font-size: 13px;
  padding: 20px 0;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.session-item:hover {
  background: #2d2e3a;
}

.session-item.active {
  background: #2563eb20;
  border: 1px solid #2563eb40;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  color: #e0e0e0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
  display: flex;
  gap: 8px;
}

.session-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.tool-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: #2d2e3a;
  border-radius: 3px;
  color: #8b8d9a;
}

.tool-tag.more {
  background: #3d3e4a;
  color: #aaa;
}

.delete-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  opacity: 0;
  transition: opacity 0.15s;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444;
}

/* 删除确认对话框 */
.delete-confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.delete-confirm-dialog {
  background: #1a1b23;
  border: 1px solid #2d2e3a;
  border-radius: 8px;
  padding: 20px;
  min-width: 300px;
  max-width: 400px;
}

.delete-confirm-title {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 12px;
}

.delete-confirm-body {
  font-size: 14px;
  color: #aaa;
  margin-bottom: 20px;
  line-height: 1.5;
}

.delete-confirm-hint {
  font-size: 12px;
  color: #666;
}

.delete-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.delete-confirm-cancel {
  padding: 6px 16px;
  background: #2d2e3a;
  border: none;
  border-radius: 4px;
  color: #aaa;
  cursor: pointer;
}

.delete-confirm-cancel:hover {
  background: #3d3e4a;
}

.delete-confirm-ok {
  padding: 6px 16px;
  background: #ef4444;
  border: none;
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
}

.delete-confirm-ok:hover {
  background: #dc2626;
}
</style>
