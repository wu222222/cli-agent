<template>
  <div class="history-container">
    <div class="history-header">
      <h2>历史记录</h2>
      <button class="clear-btn" @click="clearAll">清空历史</button>
    </div>

    <div class="history-list">
      <div
        v-for="(item, index) in history"
        :key="index"
        class="history-item"
      >
        <div class="history-preview">
          <p class="history-query">{{ item.query }}</p>
          <p class="history-response">{{ item.response }}</p>
        </div>
      </div>

      <div v-if="history.length === 0" class="empty-state">
        <p>暂无历史记录</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getHistory, clearHistory } from '@/api/agent'

interface HistoryItem {
  query: string
  response: string
}

const history = ref<HistoryItem[]>([])

const loadHistory = async () => {
  try {
    const data = await getHistory()
    history.value = data as HistoryItem[]
  } catch {
    history.value = []
  }
}

const clearAll = async () => {
  try {
    await clearHistory()
    history.value = []
  } catch {
    // ignore
  }
}

onMounted(loadHistory)
</script>

<style lang="scss">
.history-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  h2 {
    color: #fff;
    font-size: 18px;
    font-weight: 600;
    margin: 0;
  }

  .clear-btn {
    padding: 6px 16px;
    background: rgba(220, 53, 69, 0.2);
    color: #dc3545;
    border: 1px solid rgba(220, 53, 69, 0.3);
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: rgba(220, 53, 69, 0.3);
    }
  }
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;

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

.history-item {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  margin-bottom: 8px;

  .history-preview {
    .history-query {
      color: #fff;
      font-size: 14px;
      margin: 0 0 8px;
      font-weight: 500;
    }

    .history-response {
      color: rgba(255, 255, 255, 0.6);
      font-size: 13px;
      margin: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.5);

  p {
    font-size: 14px;
  }
}
</style>
