<template>
  <div class="history-container">
    <div class="history-header">
      <h2>历史记录</h2>
      <button class="clear-btn" @click="clearHistory">清空历史</button>
    </div>

    <div class="history-list">
      <div
        v-for="(item, index) in history"
        :key="index"
        class="history-item"
        @click="loadHistory(item)"
      >
        <div class="history-preview">
          <p class="history-query">{{ item.query }}</p>
          <p class="history-time">{{ item.timestamp }}</p>
        </div>
        <button class="delete-btn" @click.stop="deleteHistory(index)">删除</button>
      </div>

      <div v-if="history.length === 0" class="empty-state">
        <span class="empty-icon">📋</span>
        <p>暂无历史记录</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface HistoryItem {
  query: string
  response: string
  timestamp: string
}

const history = ref<HistoryItem[]>([
  {
    query: '列出当前目录下的文件',
    response: '已执行 ls -la 命令',
    timestamp: '2024-01-15 14:30:00'
  },
  {
    query: '查找最大的5个文件',
    response: '已执行 du -ah . | sort -rh | head -n 5',
    timestamp: '2024-01-15 14:25:00'
  }
])

const loadHistory = (item: HistoryItem) => {
  console.log('Loading history:', item)
}

const deleteHistory = (index: number) => {
  history.value.splice(index, 1)
}

const clearHistory = () => {
  history.value = []
}
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    transform: translateX(4px);
  }

  .history-preview {
    flex: 1;
    min-width: 0;

    .history-query {
      color: #fff;
      font-size: 14px;
      margin: 0 0 4px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .history-time {
      color: rgba(255, 255, 255, 0.5);
      font-size: 12px;
      margin: 0;
    }
  }

  .delete-btn {
    padding: 4px 8px;
    background: transparent;
    color: rgba(255, 255, 255, 0.5);
    border: none;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    opacity: 0;
    transition: all 0.2s;

    &:hover {
      background: rgba(220, 53, 69, 0.2);
      color: #dc3545;
    }
  }

  &:hover .delete-btn {
    opacity: 1;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.5);

  .empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  p {
    font-size: 14px;
  }
}
</style>