import { ref } from 'vue'

interface ToastOptions {
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
  actionText?: string
  onAction?: () => void
}

const toastState = ref<ToastOptions | null>(null)

export function useToast() {
  function showToast(options: ToastOptions) {
    toastState.value = options
    // 如果没有操作按钮，自动清除
    if (!options.actionText) {
      setTimeout(() => {
        if (toastState.value === options) {
          toastState.value = null
        }
      }, options.duration || 3000)
    }
  }

  function success(message: string, duration?: number) {
    showToast({ message, type: 'success', duration })
  }

  function error(message: string, duration?: number) {
    showToast({ message, type: 'error', duration })
  }

  function warning(message: string, duration?: number) {
    showToast({ message, type: 'warning', duration })
  }

  function info(message: string, duration?: number) {
    showToast({ message, type: 'info', duration })
  }

  function action(message: string, actionText: string, onAction: () => void) {
    showToast({ message, type: 'warning', actionText, onAction })
  }

  function handleAction() {
    if (toastState.value?.onAction) {
      toastState.value.onAction()
    }
    toastState.value = null
  }

  return {
    toastState,
    showToast,
    success,
    error,
    warning,
    info,
    action,
    handleAction,
  }
}
