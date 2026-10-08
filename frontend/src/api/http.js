import axios from 'axios'
import { ElMessage } from 'element-plus'

export const TOKEN_KEY = 'merchpilot_token'
export const USER_KEY = 'merchpilot_user'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 401 时清理登录态并跳回登录页；其它错误统一弹出后端返回的中文提示。 */
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (!window.location.hash.includes('/login')) {
        window.location.hash = '#/login'
        ElMessage.warning('登录状态已失效，请重新登录')
      }
      return Promise.reject(error)
    }

    let message = '请求失败，请稍后重试'
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      // FastAPI 参数校验错误
      message = detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('；')
    } else if (status === 403) {
      message = '当前角色无权执行该操作'
    } else if (status === 404) {
      message = '请求的资源不存在'
    } else if (error.message) {
      message = error.message
    }

    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default http
