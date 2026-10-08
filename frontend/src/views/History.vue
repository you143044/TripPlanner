<template>
  <div class="history-container">
    <div class="page-header">
      <a-button class="back-btn" @click="goHome">← 返回首页</a-button>
      <h1 class="page-title">📋 我的旅行记录</h1>
      <p class="page-subtitle">本设备上生成过的所有旅行计划</p>
    </div>

    <a-card class="history-card" :bordered="false">
      <a-spin :spinning="loading">
        <a-empty v-if="!loading && items.length === 0" description="暂无历史记录,快去生成第一个旅行计划吧~">
          <template #image>
            <div style="font-size: 56px;">🗺️</div>
          </template>
          <a-button type="primary" @click="goHome">开始规划旅行</a-button>
        </a-empty>

        <a-table
          v-else
          :columns="columns"
          :data-source="items"
          :pagination="pagination"
          row-key="task_id"
          :loading="loading"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <!-- 状态列 -->
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">
                {{ statusText(record.status) }}
              </a-tag>
            </template>

            <!-- 城市列 -->
            <template v-else-if="column.key === 'city'">
              <span class="city-name">{{ record.city }}</span>
              <span v-if="record.status === 'success'" class="city-meta">
                {{ record.travel_days }}天 · {{ record.start_date }}~{{ record.end_date }}
              </span>
            </template>

            <!-- 偏好列 -->
            <template v-else-if="column.key === 'preferences'">
              <a-tag v-for="p in record.preferences" :key="p" color="purple" class="pref-tag">{{ p }}</a-tag>
              <span v-if="!record.preferences || record.preferences.length === 0" class="muted">—</span>
            </template>

            <!-- 额外要求列 -->
            <template v-else-if="column.key === 'free_text'">
              <span :title="record.free_text_input" class="free-text">{{ record.free_text_input || '—' }}</span>
            </template>

            <!-- 创建时间列 -->
            <template v-else-if="column.key === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>

            <!-- 操作列 -->
            <template v-else-if="column.key === 'action'">
              <a-button
                v-if="record.status === 'success'"
                type="primary"
                size="small"
                ghost
                @click="openPlan(record)"
              >查看详情</a-button>
              <span v-else-if="record.status === 'failed'" class="muted" :title="record.error_message">已失败</span>
            </template>
          </template>
        </a-table>
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getTripHistory, getTaskStatus } from '@/services/api'
import type { HistoryRecord } from '@/types'

const router = useRouter()
const loading = ref(false)
const items = ref<HistoryRecord[]>([])
const total = ref(0)
const pageSize = ref(10)

const columns = [
  { title: '状态', key: 'status', width: 90 },
  { title: '城市 / 日期', key: 'city' },
  { title: '偏好', key: 'preferences' },
  { title: '额外要求', key: 'free_text', ellipsis: true },
  { title: '生成时间', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 100, align: 'center' as const }
]

const pagination = computed(() => ({
  total: total.value,
  current: Math.floor(offset / pageSize.value) + 1,
  pageSize: pageSize.value,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条记录`
}))

let offset = 0

const loadHistory = async () => {
  loading.value = true
  try {
    const res = await getTripHistory(pageSize.value, offset)
    items.value = res.items || []
    total.value = res.total || 0
  } catch (e: any) {
    message.error(e.message || '加载历史记录失败')
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag: { current?: number; pageSize?: number }) => {
  pageSize.value = pag.pageSize || 10
  offset = ((pag.current || 1) - 1) * pageSize.value
  loadHistory()
}

const openPlan = async (record: HistoryRecord) => {
  // 优先用已有摘要数据；列表接口不含完整计划,需拉取任务详情
  try {
    const detail = await getTaskStatus(record.task_id)
    if (detail.data) {
      sessionStorage.setItem('tripPlan', JSON.stringify(detail.data))
      router.push('/result')
    } else {
      message.error('该记录没有可用数据')
    }
  } catch (e: any) {
    message.error(e.message || '加载计划详情失败')
  }
}

const statusColor = (s: string) => ({ success: 'green', failed: 'red', pending: 'orange', processing: 'blue' } as Record<string, string>)[s] || 'default'
const statusText = (s: string) => ({ success: '成功', failed: '失败', pending: '排队中', processing: '生成中' } as Record<string, string>)[s] || s

const formatTime = (t?: string) => {
  if (!t) return '—'
  try {
    const d = new Date(t)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return t
  }
}

const goHome = () => router.push('/')

onMounted(loadHistory)
</script>

<style scoped>
.history-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px 60px;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;
  position: relative;
}

.back-btn {
  position: absolute;
  left: 20px;
  top: 0;
  border-radius: 20px;
}

.page-title {
  font-size: 34px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 8px;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.9);
  font-size: 15px;
  margin: 0;
}

.history-card {
  max-width: 1200px;
  margin: 0 auto;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.city-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.city-meta {
  display: block;
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.pref-tag {
  margin: 2px;
  font-size: 12px;
}

.free-text {
  color: #666;
  font-size: 13px;
  display: block;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.muted {
  color: #bbb;
}

@media (max-width: 768px) {
  .history-container { padding: 20px 8px 40px; }
  .page-title { font-size: 24px; }
  .back-btn { left: 8px; font-size: 12px; }
}
</style>