import axios from 'axios'
import type { TripFormData, TaskInfo, TaskDetail, HistoryResponse } from '@/types'

// 生产环境默认同源(由nginx代理/api到后端),本地开发用localhost:8000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '/' : 'http://localhost:8000')

const USER_ID_KEY = 'trip_planner_user_id'

/** 获取或生成本地用户标识(UUID),用于服务端区分不同用户 */
export function getOrCreateUserId(): string {
  let userId = localStorage.getItem(USER_ID_KEY)
  if (!userId) {
    // browser-safe UUID 生成
    userId = (crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`)
    localStorage.setItem(USER_ID_KEY, userId)
  }
  return userId
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000, // 提交/查询接口快,轮询时每轮单独计时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器: 自动附带用户标识
apiClient.interceptors.request.use(
  (config) => {
    config.headers['X-User-Id'] = getOrCreateUserId()
    return config
  },
  (error) => Promise.reject(error)
)

/**
 * 提交旅行计划生成任务(异步,立即返回task_id)
 */
export async function submitTripPlan(formData: TripFormData): Promise<TaskInfo> {
  try {
    const response = await apiClient.post<TaskInfo>('/api/trip/plan', formData)
    return response.data
  } catch (error: any) {
    console.error('提交旅行计划任务失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '提交失败,请稍后重试')
  }
}

/**
 * 轮询任务状态
 */
export async function getTaskStatus(taskId: string): Promise<TaskDetail> {
  try {
    const response = await apiClient.get<TaskDetail>(`/api/trip/plan/${taskId}`)
    return response.data
  } catch (error: any) {
    console.error('查询任务状态失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '查询任务状态失败')
  }
}

/**
 * 查询当前用户的历史生成记录
 */
export async function getTripHistory(limit = 50, offset = 0): Promise<HistoryResponse> {
  try {
    const response = await apiClient.get<HistoryResponse>('/api/trip/history', {
      params: { limit, offset }
    })
    return response.data
  } catch (error: any) {
    console.error('查询历史记录失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '查询历史记录失败')
  }
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

export default apiClient