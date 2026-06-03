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
import { ref, watch, computed } from 'vue'

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

watch(() => props.message, (msg) => {
  if (msg) {
    visible.value = true
    // 如果有操作按钮，不自动关闭
    if (!props.actionText) {
      setTimeout(() => {
        visible.value = false
      }, props.duration || 3000)
    }
  }
})
</script>

<style scoped>
.toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
}

.toast.success {
  background: rgba(34, 197, 94, 0.9);
  color: white;
}

.toast.error {
  background: rgba(239, 68, 68, 0.9);
  color: white;
}

.toast.warning {
  background: rgba(234, 179, 8, 0.9);
  color: black;
}

.toast.info {
  background: rgba(59, 130, 246, 0.9);
  color: white;
}

.toast-icon {
  font-size: 16px;
  font-weight: bold;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}
</style>
