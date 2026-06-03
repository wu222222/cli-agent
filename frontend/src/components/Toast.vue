<template>
  <Teleport to="body">
    <Transition name="toast">
      <div v-if="visible" class="toast" :class="type">
        <span class="toast-icon">{{ icon }}</span>
        <span class="toast-message">{{ message }}</span>
        <button v-if="actionText" class="toast-action" @click="handleAction">
          {{ actionText }}
        </button>
        <button class="toast-close" @click="visible = false">×</button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'

const props = defineProps<{
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
  actionText?: string
}>()

const emit = defineEmits<{
  (e: 'action'): void
}>()

const visible = ref(false)

const icon = computed(() => {
  switch (props.type) {
    case 'success': return '✓'
    case 'error': return '✕'
    case 'warning': return '⚠'
    default: return 'ℹ'
  }
})

function handleAction() {
  emit('action')
  visible.value = false
}

function showToast() {
  visible.value = true
  // 如果有操作按钮，不自动关闭
  if (!props.actionText) {
    setTimeout(() => {
      visible.value = false
    }, props.duration || 3000)
  }
}

// 组件挂载时显示（v-if 创建时）
onMounted(() => {
  if (props.message) {
    showToast()
  }
})

// 监听后续变化
watch(() => props.message, (msg) => {
  if (msg) {
    showToast()
  }
})
</script>

<style scoped>
.toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-radius: 10px;
  font-size: 13px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  max-width: 400px;
}

.toast.success {
  background: rgba(34, 197, 94, 0.95);
  color: white;
}

.toast.error {
  background: rgba(239, 68, 68, 0.95);
  color: white;
}

.toast.warning {
  background: rgba(45, 46, 58, 0.95);
  color: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(234, 179, 8, 0.4);
}

.toast.info {
  background: rgba(59, 130, 246, 0.95);
  color: white;
}

.toast-icon {
  font-size: 15px;
  font-weight: 600;
  opacity: 0.9;
}

.toast-message {
  flex: 1;
  line-height: 1.4;
}

.toast-action {
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: inherit;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.toast-action:hover {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.3);
}

.toast-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: none;
  border: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 18px;
  border-radius: 4px;
  transition: all 0.15s;
}

.toast-close:hover {
  opacity: 0.8;
  background: rgba(255, 255, 255, 0.1);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
