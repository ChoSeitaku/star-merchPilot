<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProductStore } from '@/stores/product'
import StatusTag from '@/components/StatusTag.vue'
import { formatMoney, formatPercent, platformLabel } from '@/utils/format'

// 9 个标签页，全部懒加载：只在首次激活时挂载并拉取数据
import TabProductCompetitor from './tabs/TabProductCompetitor.vue'
import TabDiagnosis from './tabs/TabDiagnosis.vue'
import TabMainImage from './tabs/TabMainImage.vue'
import TabVideo from './tabs/TabVideo.vue'
import TabJobs from './tabs/TabJobs.vue'
import TabAssets from './tabs/TabAssets.vue'
import TabLinks from './tabs/TabLinks.vue'
import TabAd from './tabs/TabAd.vue'
import TabReview from './tabs/TabReview.vue'

const route = useRoute()
const router = useRouter()
const productStore = useProductStore()

/**
 * 离开本页时 route.params.id 会短暂变为 undefined，
 * 直接 Number() 会得到 NaN 并触发一次无效请求，因此这里做有效性判断。
 */
const productId = computed(() => {
  const parsed = Number(route.params.id)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
})

const activeTab = ref(String(route.query.tab || 'product'))
/** 记录已激活过的标签页，配合 keep-alive 实现真正的懒加载 */
const visitedTabs = ref(new Set([activeTab.value]))

const tabs = [
  { name: 'product', label: '商品&竞品', icon: 'Goods' },
  { name: 'diagnosis', label: '诊断', icon: 'DataAnalysis' },
  { name: 'main-image', label: '主图', icon: 'Picture' },
  { name: 'video', label: '视频', icon: 'VideoCamera' },
  { name: 'jobs', label: '任务', icon: 'List' },
  { name: 'assets', label: '素材库', icon: 'Files' },
  { name: 'links', label: '链接', icon: 'Link' },
  { name: 'ad', label: '投放', icon: 'Promotion' },
  { name: 'review', label: '复盘', icon: 'TrendCharts' },
]

const product = computed(() => productStore.product)
const timeline = computed(() => productStore.timeline)

function onTabChange(name) {
  visitedTabs.value.add(name)
  router.replace({ query: { ...route.query, tab: name } })
}

/** 子标签页完成写操作后通知父级刷新商品信息与闭环进度 */
async function handleChanged() {
  await productStore.notifyChanged()
}

onMounted(async () => {
  if (productId.value) await productStore.load(productId.value, { force: true })
})

watch(productId, async (id) => {
  if (!id) return
  productStore.reset()
  await productStore.load(id, { force: true })
})
</script>

<template>
  <div class="page" v-loading="productStore.loading">
    <!-- 头部 -->
    <el-card shadow="never" class="detail-header-card">
      <div class="product-head">
        <div class="product-head-main">
          <div class="product-title-row">
            <h1 class="page-title">{{ product?.name || '加载中…' }}</h1>
            <StatusTag v-if="product" :value="product.status" />
            <el-tag v-if="product" size="small" effect="plain">
              {{ platformLabel(product.platform) }}
            </el-tag>
          </div>

          <div class="product-meta">
            <span>店铺：<el-link type="primary" @click="router.push(`/stores/${product?.store_id}`)">
              {{ product?.store_name }}</el-link></span>
            <span>类目：{{ product?.category || '—' }}</span>
            <span>售价：<b>{{ formatMoney(product?.price) }}</b></span>
            <span>成本：{{ formatMoney(product?.cost) }}</span>
            <span>毛利率：<b>{{ formatPercent(product?.margin_rate, 1) }}</b></span>
            <span>SKU：{{ product?.sku_count || 0 }} 个</span>
          </div>
        </div>

        <el-button :icon="'Refresh'" @click="productStore.refresh()">刷新</el-button>
      </div>

      <!-- 闭环进度 -->
      <div v-if="timeline" class="loop-progress">
        <div class="loop-progress-head">
          <span class="section-title" style="margin: 0">运营闭环进度</span>
          <span class="text-small text-muted">
            {{ timeline.completed_steps }} / {{ timeline.total_steps }} 步已完成
          </span>
        </div>
        <el-progress
          :percentage="timeline.progress_percent"
          :stroke-width="14"
          :status="timeline.progress_percent === 100 ? 'success' : undefined"
          striped
        />
        <div class="loop-steps">
          <el-tooltip v-for="step in timeline.steps" :key="step.key"
                      :content="`${step.label}：${step.detail}`" placement="top">
            <div class="loop-step" :class="{ 'is-done': step.done }">
              <el-icon v-if="step.done"><CircleCheckFilled /></el-icon>
              <el-icon v-else><Clock /></el-icon>
              <span>{{ step.label }}</span>
            </div>
          </el-tooltip>
        </div>
        <el-alert
          v-if="timeline.next_step"
          type="info"
          :closable="false"
          class="mt-12"
          :title="`下一步建议：${timeline.next_step.label}（${timeline.next_step.detail}）`"
        />
        <el-alert
          v-else
          type="success"
          :closable="false"
          class="mt-12"
          title="本商品的完整运营闭环已完成，可基于最新复盘结论开启下一轮优化"
        />
      </div>
    </el-card>

    <!-- 9 个标签页 -->
    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane v-for="tab in tabs" :key="tab.name" :name="tab.name">
          <template #label>
            <span class="tab-label">
              <el-icon><component :is="tab.icon" /></el-icon>
              {{ tab.label }}
            </span>
          </template>

          <keep-alive>
            <component
              :is="{
                product: TabProductCompetitor,
                diagnosis: TabDiagnosis,
                'main-image': TabMainImage,
                video: TabVideo,
                jobs: TabJobs,
                assets: TabAssets,
                links: TabLinks,
                ad: TabAd,
                review: TabReview,
              }[tab.name]"
              v-if="visitedTabs.has(tab.name)"
              :product-id="productId"
              :active="activeTab === tab.name"
              @changed="handleChanged"
            />
          </keep-alive>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.product-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.product-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.product-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 10px;
  font-size: 13px;
  color: #606266;
}

.loop-progress {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--mp-border);
}

.loop-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.loop-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.loop-step {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 3px 9px;
  border-radius: 12px;
  background: #f4f4f5;
  color: #909399;
}

.loop-step.is-done {
  background: #f0f9eb;
  color: #67c23a;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
</style>
