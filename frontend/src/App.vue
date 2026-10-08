<template>
  <div id="app">
    <a-layout style="min-height: 100vh">
      <a-layout-header class="app-header">
        <div class="header-left">
          <div class="header-title">🌍 HelloAgents智能旅行助手</div>
        </div>
        <div class="header-right">
          <router-link to="/" class="header-link">🏠 首页</router-link>
          <router-link to="/history" class="header-link">📋 我的历史</router-link>
        </div>
      </a-layout-header>
      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>
      <a-layout-footer style="text-align: center">
        HelloAgents智能旅行助手 ©2025 基于HelloAgents框架
      </a-layout-footer>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif;
}

.app-header {
  background: #001529;
  padding: 0 50px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-title {
  color: white;
  font-size: 24px;
  font-weight: bold;
}

.header-right {
  display: flex;
  gap: 20px;
}

.header-link {
  color: rgba(255, 255, 255, 0.85);
  font-size: 15px;
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 18px;
  transition: all 0.3s;
}

.header-link:hover,
.header-link.router-link-active {
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
}

.app-content {
  padding: 24px;
}

@media (max-width: 768px) {
  .app-header { padding: 0 12px !important; }
  .app-content { padding: 8px !important; }
  .header-title { font-size: 16px !important; }
  .header-link { font-size: 13px !important; padding: 4px 8px !important; }
  .header-right { gap: 8px !important; }
}
</style>

