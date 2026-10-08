<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { workspaceApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import StatusTag from '@/components/StatusTag.vue'
import { PLATFORM_OPTIONS, platformLabel } from '@/utils/format'

const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const loading = ref(false)
const creatingDemo = ref(false)
const platform = ref('')
const dashboard = ref(null)

const stores = computed(() => dashboard.value?.stores || [])
const lowStock = computed(() => dashboard.value?.low_stock || { total: 0, items: [] })
const productPool = computed(() => dashboard.value?.product_pool || {})
const loopProgress = computed(() => dashboard.value?.loop_progress || {})
const jobs = computed(() => dashboard.value?.jobs || { by_status: {} })
const platformStats = computed(() => dashboard.value?.platform_filter?.store_platforms || [])

const loopSteps = [
  { key: 'diagnoses', label: '诊断' },
  { key: 'main_image_plans', label: '主图方案' },
  { key: 'video_scripts', label: '视频脚本' },
  { key: 'assets', label: '素材' },
  { key: 'approved_assets', label: '已审素材' },
  { key: 'ad_recommendations', label: '投放建议' },
  { key: 'confirmed_ads', label: '已确认投放' },
  { key: 'review_reports', label: '复盘报告' },
]

async function load() {
  loading.value = true
  try {
    dashboard.value = await workspaceApi.dashboard({ platform: platform.value || undefined })
  } finally {
    loading.value = false
  }
}

function onPlatformChange() {
  load()
}

function goProductPool() {
  router.push({ path: '/products', query: platform.value ? { platform: platform.value } : {} })
}

async function createDemoData() {
  try {
    await ElMessageBox.confirm(
      '将一次性创建店铺、平台账号占位、商品、SKU、库存、竞品、方案、素材、链接、投放建议、实验、经营数据与复盘报告，用于完整体验闭环。是否继续？',
      '创建演示数据',
      { confirmButtonText: '创建', cancelButtonText: '取消', type: 'info' },
    )
  } catch {
    return
  }

  creatingDemo.value = true
  try {
    const result = await workspaceApi.demoData(false)
    if (result.created) {
      ElMessage.success(result.message)
      await load()
      if (result.product_id) {
        router.push(`/products/${result.product_id}`)
      }
    } else {
      ElMessage.info(result.message)
    }
  } finally {
    creatingDemo.value = false
  }
}

onMounted(async () => {
  await load()
  app.fetchWorkerStatus().catch(() => {})
})
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h1 class="page-title">首页工作台</h1>
        <p class="page-subtitle">
          当前角色：{{ auth.displayName }}（<StatusTag :value="auth.role" />）·
          内容生成：{{ app.activeProviderLabel }}
        </p>
      </div>

      <div class="toolbar">
        <el-select
          v-model="platform"
          placeholder="全部平台"
          clearable
          style="width: 150px"
          @change="onPlatformChange"
        >
          <el-option
            v-for="item in PLATFORM_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button :icon="'Refresh'" @click="load">刷新</el-button>
        <el-button v-permission="['admin']" type="primary" :icon="'MagicStick'"
                   :loading="creatingDemo" @click="createDemoData">
          创建演示数据
        </el-button>
      </div>
    </div>

    <!-- 关键指标 -->
    <el-row :gutter="14" class="mb-12">
      <el-col :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value">{{ stores.length }}</div>
          <div class="stat-label">店铺数</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value">{{ productPool.total_products || 0 }}</div>
          <div class="stat-label">商品池商品数</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value" :class="{ 'text-warning': lowStock.total > 0 }">
            {{ lowStock.total }}
          </div>
          <div class="stat-label">低库存 SKU</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value">{{ productPool.active_products || 0 }}</div>
          <div class="stat-label">在售商品</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value">{{ jobs.by_status?.running || 0 }}</div>
          <div class="stat-label">执行中任务</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value">{{ jobs.by_status?.failed || 0 }}</div>
          <div class="stat-label">失败任务</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14">
      <!-- 店铺卡片 -->
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="mb-12">
          <template #header>
            <div class="card-header">
              <span class="section-title" style="margin: 0">店铺</span>
              <div class="toolbar">
                <el-button v-permission="['admin']" size="small" :icon="'Plus'"
                           @click="router.push('/stores')">
                  创建店铺
                </el-button>
                <el-button size="small" text @click="router.push('/stores')">全部店铺</el-button>
              </div>
            </div>
          </template>

          <el-empty v-if="!stores.length" description="暂无店铺，可先创建店铺或一键生成演示数据"
                    :image-size="80" />

          <div v-else class="store-grid">
            <div v-for="store in stores" :key="store.id" class="store-card"
                 @click="router.push(`/stores/${store.id}`)">
              <div class="store-card-head">
                <span class="store-name">{{ store.store_name }}</span>
                <el-tag size="small" effect="plain">{{ platformLabel(store.platform) }}</el-tag>
              </div>
              <div class="store-metrics">
                <span>商品 <b>{{ store.product_count }}</b></span>
                <span :class="{ 'text-warning': store.low_stock_count > 0 }">
                  库存预警 <b>{{ store.low_stock_count }}</b>
                </span>
              </div>
              <div class="store-owner text-small text-muted">负责人：{{ store.owner_name || '—' }}</div>
            </div>
          </div>

          <div v-if="platformStats.length" class="platform-stats mt-12">
            <span class="text-small text-muted">平台分布：</span>
            <el-tag v-for="item in platformStats" :key="item.platform" size="small" effect="plain"
                    class="platform-tag">
              {{ platformLabel(item.platform) }} {{ item.count }}
            </el-tag>
          </div>
        </el-card>

        <!-- 商品池入口 -->
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="section-title" style="margin: 0">商品池</span>
              <el-button size="small" type="primary" :icon="'Right'" @click="goProductPool">
                进入商品池
              </el-button>
            </div>
          </template>
          <el-row :gutter="12">
            <el-col v-for="item in [
              { key: 'total_products', label: '全部商品', type: 'info' },
              { key: 'active_products', label: '在售', type: 'success' },
              { key: 'draft_products', label: '草稿', type: 'info' },
              { key: 'inactive_products', label: '已停用', type: 'warning' },
            ]" :key="item.key" :span="6">
              <div class="pool-item">
                <el-tag :type="item.type" size="small" effect="plain">{{ item.label }}</el-tag>
                <div class="pool-value">{{ productPool[item.key] || 0 }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>

      <!-- 右侧 -->
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="mb-12">
          <template #header>
            <div class="card-header">
              <span class="section-title" style="margin: 0">
                低库存提示
                <el-tag v-if="lowStock.total" type="warning" size="small" effect="dark">
                  {{ lowStock.total }}
                </el-tag>
              </span>
            </div>
          </template>

          <el-empty v-if="!lowStock.items.length" description="库存水位正常" :image-size="70" />
          <div v-else class="low-stock-list">
            <div v-for="item in lowStock.items" :key="item.sku_id" class="low-stock-item"
                 @click="router.push(`/products/${item.product_id}`)">
              <div class="low-stock-main">
                <div class="low-stock-name">{{ item.product_name }}</div>
                <div class="text-small text-muted">{{ item.sku_code }} · {{ item.sku_name }}</div>
              </div>
              <el-tag type="danger" size="small" effect="plain">
                库存 {{ item.stock_qty }} / 阈值 {{ item.warning_threshold }}
              </el-tag>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="mb-12">
          <template #header>
            <span class="section-title" style="margin: 0">闭环进度统计</span>
          </template>
          <div class="loop-grid">
            <div v-for="step in loopSteps" :key="step.key" class="loop-item">
              <div class="loop-value">{{ loopProgress[step.key] || 0 }}</div>
              <div class="loop-label">{{ step.label }}</div>
            </div>
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <span class="section-title" style="margin: 0">快捷入口</span>
          </template>
          <div class="quick-actions">
            <el-button :icon="'Goods'" @click="router.push('/products')">商品池</el-button>
            <el-button :icon="'Upload'" @click="router.push('/imports')">导入中心</el-button>
            <el-button :icon="'Shop'" @click="router.push('/stores')">店铺管理</el-button>
            <el-button :icon="'Setting'" @click="router.push('/settings')">系统设置</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.store-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.store-card {
  border: 1px solid var(--mp-border);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.18s;
}

.store-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 4px 14px rgba(64, 158, 255, 0.16);
}

.store-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.store-name {
  font-weight: 600;
  font-size: 14.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.store-metrics {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.text-warning {
  color: var(--el-color-warning);
}

.platform-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.platform-tag {
  margin-right: 0;
}

.pool-item {
  text-align: center;
  padding: 8px 0;
}

.pool-value {
  font-size: 20px;
  font-weight: 600;
  margin-top: 6px;
}

.low-stock-list {
  max-height: 300px;
  overflow-y: auto;
}

.low-stock-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--mp-border);
  cursor: pointer;
}

.low-stock-item:last-child {
  border-bottom: none;
}

.low-stock-name {
  font-size: 13.5px;
  font-weight: 500;
}

.loop-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.loop-item {
  text-align: center;
  padding: 8px 4px;
  background: #fafbfc;
  border-radius: 6px;
}

.loop-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.loop-label {
  font-size: 12px;
  color: var(--mp-text-muted);
  margin-top: 2px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-actions :deep(.el-button) {
  margin-left: 0;
}
</style>
