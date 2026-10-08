// 类型定义

export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  ticket_price?: number
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
}

export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan
}

/** 提交生成任务后的响应 */
export interface TaskInfo {
  success: boolean
  task_id: string
  status: 'pending' | 'processing' | 'success' | 'failed'
  message: string
  queue_position?: number
}

/** 任务状态详情(轮询结果) */
export interface TaskDetail {
  success: boolean
  task_id: string
  status: 'pending' | 'processing' | 'success' | 'failed'
  step?: string
  step_label?: string
  queue_position?: number
  duration_ms?: number
  error_message?: string
  data?: TripPlan
}

/** 历史记录摘要 */
export interface HistoryRecord {
  task_id: string
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
  status: 'pending' | 'processing' | 'success' | 'failed'
  duration_ms?: number
  error_message?: string
  created_at?: string
}

/** 历史记录列表响应 */
export interface HistoryResponse {
  success: boolean
  items: HistoryRecord[]
  total: number
}

