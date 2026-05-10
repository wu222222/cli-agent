import { ref } from 'vue'
import { connectStream } from '@/api/agent'
import { useChatStore } from '@/stores/chat'

export function useSSE() {
  const eventSource = ref<EventSource | null>(null)

  function connect(requestId: string) {
    const chatStore = useChatStore()

    eventSource.value = connectStream(requestId, {
      onToolStart(_data) {
        // 简洁模式：隐藏 tool_start 事件，不显示"正在执行"气泡
      },

      onToolResult(data) {
        chatStore.pushMessage({
          role: 'system',
          content: data.content,
          timestamp: new Date().toLocaleTimeString(),
          thought: '',
          type: 'tool_result',
          agent: data.agent || 'WorkerAgent',
          toolName: data.tool,
          command: data.command || '',
        })
      },

      onConfirm(data) {
        chatStore.setPending({
          content: data.content,
          requestId,
          thought: data.thought,
          command: data.command,
        })
      },

      onFinal(data) {
        chatStore.pushMessage({
          role: 'system',
          content: data.content,
          timestamp: new Date().toLocaleTimeString(),
          thought: '',
          type: 'text',
          agent: data.agent || 'Agent',
        })
        chatStore.isThinking = false
        disconnect()
      },

      onError(data) {
        chatStore.pushMessage({
          role: 'system',
          content: `错误: ${data.content}`,
          timestamp: new Date().toLocaleTimeString(),
          thought: '',
          type: 'text',
          agent: 'System',
        })
        chatStore.isThinking = false
        disconnect()
      },

      onOpen() {
        chatStore.isConnected = true
      },
    })

    // 额外监听 thought 事件（connectStream 不处理的自定义事件）
    if (eventSource.value) {
      eventSource.value.addEventListener('thought', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        chatStore.pushMessage({
          role: 'system',
          content: data.content,
          timestamp: new Date().toLocaleTimeString(),
          thought: '',
          type: 'thought',
          agent: data.agent || 'Agent',
        })
      })
    }
  }

  function disconnect() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  return { connect, disconnect, eventSource }
}
