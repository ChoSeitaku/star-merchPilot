import { defineStore } from 'pinia'
import { productApi } from '@/api'

/**
 * 商品详情页共享状态。
 * 9 个标签页都从这里取商品基础信息与闭环进度，避免切换标签时重复请求。
 */
export const useProductStore = defineStore('product', {
  state: () => ({
    productId: null,
    product: null,
    timeline: null,
    loading: false,
    /** 任一标签页完成写操作后自增，其它标签页可据此刷新 */
    revision: 0,
  }),

  getters: {
    storeName: (state) => state.product?.store_name || '',
    productName: (state) => state.product?.name || '',
    progressPercent: (state) => state.timeline?.progress_percent ?? 0,
    skus: (state) => state.product?.skus || [],
    mappings: (state) => state.product?.mappings || [],
  },

  actions: {
    async load(productId, { force = false } = {}) {
      if (!force && this.productId === productId && this.product) return this.product
      this.loading = true
      this.productId = productId
      try {
        const [product, timeline] = await Promise.all([
          productApi.detail(productId),
          productApi.timeline(productId),
        ])
        this.product = product
        this.timeline = timeline
        return product
      } finally {
        this.loading = false
      }
    },

    async refresh() {
      if (!this.productId) return
      await this.load(this.productId, { force: true })
    },

    async refreshTimeline() {
      if (!this.productId) return
      this.timeline = await productApi.timeline(this.productId)
    },

    /** 写操作完成后调用：刷新数据并通知其它标签页 */
    async notifyChanged() {
      this.revision += 1
      await this.refresh()
    },

    reset() {
      this.productId = null
      this.product = null
      this.timeline = null
    },
  },
})
