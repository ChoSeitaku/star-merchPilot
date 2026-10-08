import { defineStore } from 'pinia'
import { authApi } from '@/api'
import { TOKEN_KEY, USER_KEY } from '@/api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    role: (state) => state.user?.role || '',
    displayName: (state) => state.user?.display_name || state.user?.username || '',
    /** 是否可以执行写操作（管理员与运营人员） */
    canEdit: (state) => ['admin', 'operator'].includes(state.user?.role),
    /** 是否可以管理用户与店铺 */
    isAdmin: (state) => state.user?.role === 'admin',
    /** 是否可以确认投放建议与更新实验状态 */
    canConfirmAd: (state) => ['admin', 'operator'].includes(state.user?.role),
  },

  actions: {
    async login(payload) {
      const data = await authApi.login(payload)
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem(TOKEN_KEY, this.token)
      localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      return data
    },

    /** 刷新页面后用令牌换回最新的用户信息（角色可能已被管理员调整）。 */
    async fetchMe() {
      const user = await authApi.me()
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
      return user
    },

    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },

    hasRole(roles) {
      if (!roles || roles.length === 0) return true
      return roles.includes(this.user?.role)
    },
  },
})
