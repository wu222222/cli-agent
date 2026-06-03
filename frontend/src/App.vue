<template>
  <div class="app-container">
    <router-view v-slot="{ Component }">
      <keep-alive include="ChatView,SetupView">
        <component :is="Component" />
      </keep-alive>
    </router-view>
    <Toast
      v-if="toastState"
      :message="toastState.message"
      :type="toastState.type"
      :duration="toastState.duration"
      :action-text="toastState.actionText"
      @action="handleAction"
    />
  </div>
</template>

<script setup lang="ts">
import Toast from './components/Toast.vue'
import { useToast } from './composables/useToast'

const { toastState, handleAction } = useToast()
</script>

<style lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
}

.app-container {
  height: 100%;
  width: 100%;
}

/* 全局滚动条样式（Webkit） */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

::-webkit-scrollbar-corner {
  background: transparent;
}
</style>
