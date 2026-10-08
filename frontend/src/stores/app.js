import { defineStore } from 'pinia'
import { workspaceApi } from '@/api'

export const useAppStore = defineStore('app', {
  state: () => ({
    settings: null,
    runtime: null,
    workerStatus: null,
    loading: false,
  }),

  getters: {
    queueConfig: (state) => state.runtime?.queue || {},
    /** 工作进程是否在运行（首页工作台会展示） */
    workerRunning: (state) => Boolean(state.workerStatus?.running),
    activeProviderLabel: (state) =>
      state.runtime?.active_provider === 'mock' ? '内置模拟生成' : state.runtime?.active_provider || '—',
  },

  actions: {
    async fetchSettings() {
      this.loading = true
      try {
        const data = await workspaceApi.settings()
        this.settings = data.categories
        this.runtime = data.runtime
        this.workerStatus = data.runtime?.worker
        return data
      } finally {
        this.loading = false
      }
    },

    async fetchWorkerStatus() {
      this.workerStatus = await workspaceApi.workerStatus()
      return this.workerStatus
    },

    async updateSettings(items) {
      const result = await workspaceApi.updateSettings({ items })
      await this.fetchSettings()
      return result
    },
  },
})
