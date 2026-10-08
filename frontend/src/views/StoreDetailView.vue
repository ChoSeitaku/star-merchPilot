<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { storeApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import AiBlock from '@/components/AiBlock.vue'
import {
  PLATFORM_OPTIONS,
  formatDateTime,
  formatMoney,
  formatNumber,
  platformLabel,
} from '@/utils/format'

const route = useRoute()
const router = useRouter()
const storeId = Number(route.params.id)

const loading = ref(false)
const store = ref(null)
const advice = ref(null)
const adviceLoading = ref(false)
const activeTab = ref('products')

// 平台账号占位弹窗
const accountDialog = ref(false)
const accountForm = reactive({ platform: 'taobao', account_name: '', remark: '' })
const authorizationDialog = ref(false)
const authorizationInfo = ref(null)
const currentAccount = ref(null)

const overview = computed(() => store.value?.inventory_overview || {})

async function load() {
  loading.value = true
  try {
    store.value = await storeApi.detail(storeId)
  } finally {
    loading.value = false
  }
}

async function generateAdvice() {
  adviceLoading.value = true
  try {
    advice.value = await storeApi.inventoryAdvice(storeId)
    ElMessage.success('库存建议已生成')
  } finally {
    adviceLoading.value = false
  }
}

function openAccountDialog() {
  Object.assign(accountForm, { platform: 'taobao', account_name: '', remark: '' })
  accountDialog.value = true
}

async function createAccount() {
  await storeApi.createAccount(storeId, { ...accountForm })
  ElMessage.success('平台账号占位已创建')
  accountDialog.value = false
  await load()
}

async function startAuthorization(account) {
  currentAccount.value = account
  authorizationInfo.value = await storeApi.startAuthorization(storeId, account.id, {
    redirect_uri: `${window.location.origin}/#/stores/${storeId}`,
    scope: 'item_read,order_read',
  })
  authorizationDialog.value = true
  await load()
}

/** 演示用：模拟平台侧完成授权后回填元数据 */
async function confirmAuthorization() {
  await storeApi.authorizationCallback(storeId, currentAccount.value.id, {
    auth_code_masked: 'demo****code',
    granted_scope: 'item_read,order_read',
    authorized_account_name: currentAccount.value.account_name,
    expires_at: new Date(Date.now() + 30 * 864e5).toISOString(),
  })
  ElMessage.success('授权元数据已保存（仅安全元数据，不含任何明文凭据）')
  authorizationDialog.value = false
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ store?.store_name || '店铺详情' }}</h1>
        <p class="page-subtitle">
          <el-tag size="small" effect="plain">{{ platformLabel(store?.platform) }}</el-tag>
          <span class="ml-8">负责人：{{ store?.owner_name || '—' }}</span>
          <span class="ml-8">更新：{{ formatDateTime(store?.updated_at) }}</span>
        </p>
      </div>
      <div class="toolbar">
        <el-button :icon="'Refresh'" @click="load">刷新</el-button>
        <el-button v-permission="['admin']" :icon="'Key'" @click="openAccountDialog">
          新增平台账号
        </el-button>
        <el-button v-permission="['admin', 'operator']" type="primary" :icon="'MagicStick'"
                   :loading="adviceLoading" @click="generateAdvice">
          生成库存建议
        </el-button>
      </div>
    </div>

    <!-- 库存概览 -->
    <el-row :gutter="14" class="mb-12">
      <el-col v-for="item in [
        { label: 'SKU 数', value: overview.sku_count || 0 },
        { label: '总库存', value: overview.total_stock || 0 },
        { label: '已锁定', value: overview.total_locked || 0 },
        { label: '可用库存', value: overview.total_available || 0 },
        { label: '低库存 SKU', value: overview.low_stock_sku_count || 0, warn: true },
      ]" :key="item.label" :xs="12" :sm="8" :md="4">
        <el-card shadow="never" body-style="padding:14px 16px">
          <div class="stat-value" :class="{ 'text-warning': item.warn && item.value > 0 }">
            {{ formatNumber(item.value) }}
          </div>
          <div class="stat-label">{{ item.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab" class="store-tabs">
      <!-- 商品列表 -->
      <el-tab-pane label="店铺商品" name="products">
        <el-card shadow="never">
          <el-table :data="store?.products || []" stripe empty-text="该店铺下暂无商品">
            <el-table-column prop="name" label="商品名称" min-width="220">
              <template #default="{ row }">
                <el-link type="primary" @click="router.push(`/products/${row.id}`)">
                  {{ row.name }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="类目" width="140" />
            <el-table-column label="平台" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="价格" width="120" align="right">
              <template #default="{ row }">{{ formatMoney(row.price) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><StatusTag :value="row.status" /></template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 低库存 -->
      <el-tab-pane name="low-stock">
        <template #label>
          低库存商品
          <el-badge v-if="store?.low_stock_items?.length" :value="store.low_stock_items.length"
                    type="danger" class="tab-badge" />
        </template>
        <el-card shadow="never">
          <el-table :data="store?.low_stock_items || []" stripe empty-text="库存水位正常">
            <el-table-column prop="sku_code" label="SKU 编码" width="160">
              <template #default="{ row }"><span class="text-mono">{{ row.sku_code }}</span></template>
            </el-table-column>
            <el-table-column prop="sku_name" label="SKU 名称" min-width="180" />
            <el-table-column prop="stock_qty" label="当前库存" width="110" align="right" />
            <el-table-column prop="available_qty" label="可用库存" width="110" align="right" />
            <el-table-column prop="warning_threshold" label="预警阈值" width="110" align="right" />
            <el-table-column label="缺口" width="100" align="right">
              <template #default="{ row }">
                <el-tag type="danger" size="small" effect="plain">
                  {{ Math.max(0, row.warning_threshold - row.stock_qty) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 库存流水 -->
      <el-tab-pane label="最近库存流水" name="movements">
        <el-card shadow="never">
          <el-table :data="store?.recent_movements || []" stripe empty-text="暂无库存流水">
            <el-table-column label="时间" width="170">
              <template #default="{ row }">
                <span class="text-small">{{ formatDateTime(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="sku_code" label="SKU 编码" width="150">
              <template #default="{ row }"><span class="text-mono">{{ row.sku_code }}</span></template>
            </el-table-column>
            <el-table-column prop="movement_type" label="类型" width="100" />
            <el-table-column label="变动" width="90" align="right">
              <template #default="{ row }">
                <span :class="row.change_qty >= 0 ? 'text-success' : 'text-danger'">
                  {{ row.change_qty >= 0 ? '+' : '' }}{{ row.change_qty }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="变动前 → 变动后" width="150" align="center">
              <template #default="{ row }">{{ row.before_qty }} → {{ row.after_qty }}</template>
            </el-table-column>
            <el-table-column prop="reason_text" label="原因" min-width="180" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 平台账号占位 -->
      <el-tab-pane label="平台账号占位" name="accounts">
        <div class="compliance-note mb-12">
          合规说明：平台账号只保存授权状态与安全元数据（授权范围、占位授权链接、过期时间等），
          系统不接收也不保存明文密码、明文 token 或 cookie。
        </div>
        <el-card shadow="never">
          <el-table :data="store?.platform_accounts || []" stripe empty-text="暂无平台账号">
            <el-table-column prop="account_name" label="账号名称" min-width="180" />
            <el-table-column label="平台" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="授权状态" width="120">
              <template #default="{ row }"><StatusTag :value="row.auth_status" /></template>
            </el-table-column>
            <el-table-column label="授权范围" min-width="180">
              <template #default="{ row }">
                <span class="text-small">{{ row.auth_meta_json?.scope || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button v-permission="['admin']" size="small" text type="primary"
                           @click="startAuthorization(row)">
                  发起授权占位
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 库存建议 -->
      <el-tab-pane label="库存建议" name="advice">
        <el-card shadow="never">
          <el-empty v-if="!advice" description="尚未生成库存建议，点击右上角「生成库存建议」"
                    :image-size="80" />
          <template v-else>
            <div class="compliance-note mb-12">{{ advice.compliance_note }}</div>
            <AiBlock label="总体建议" :value="advice.summary_text" :ordered="false" />
            <el-table :data="advice.items" stripe max-height="460">
              <el-table-column prop="sku_code" label="SKU 编码" width="160">
                <template #default="{ row }"><span class="text-mono">{{ row.sku_code }}</span></template>
              </el-table-column>
              <el-table-column prop="sku_name" label="SKU 名称" min-width="150" />
              <el-table-column prop="stock_qty" label="库存" width="90" align="right" />
              <el-table-column prop="warning_threshold" label="阈值" width="90" align="right" />
              <el-table-column prop="suggested_action" label="建议动作" width="180" />
              <el-table-column prop="advice" label="说明" min-width="240" show-overflow-tooltip />
            </el-table>
          </template>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增平台账号 -->
    <el-dialog v-model="accountDialog" title="新增平台账号占位" width="480px">
      <el-alert type="warning" :closable="false" class="mb-12"
                title="请勿填写任何密码 / token / cookie，系统不接收此类信息" />
      <el-form :model="accountForm" label-width="90px">
        <el-form-item label="平台">
          <el-select v-model="accountForm.platform" style="width: 100%">
            <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                       :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号名称">
          <el-input v-model="accountForm.account_name" placeholder="例如：星航优选-主账号" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="accountForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accountDialog = false">取消</el-button>
        <el-button type="primary" @click="createAccount">创建</el-button>
      </template>
    </el-dialog>

    <!-- 授权占位 -->
    <el-dialog v-model="authorizationDialog" title="授权占位信息" width="620px">
      <el-alert type="info" :closable="false" class="mb-12"
                :title="authorizationInfo?.hint || ''" />
      <el-descriptions :column="1" border>
        <el-descriptions-item label="账号">
          {{ authorizationInfo?.account_name }}
        </el-descriptions-item>
        <el-descriptions-item label="授权状态">
          <StatusTag :value="authorizationInfo?.auth_status" />
        </el-descriptions-item>
        <el-descriptions-item label="占位授权链接">
          <div class="text-mono pre-wrap">{{ authorizationInfo?.authorize_url }}</div>
        </el-descriptions-item>
      </el-descriptions>
      <div class="compliance-note mt-12">
        真实环境应跳转平台官方 OAuth 授权页；本系统只生成占位链接与状态，
        不做任何凭据采集或代持。点击下方按钮可模拟「平台侧授权完成后回填元数据」。
      </div>
      <template #footer>
        <el-button @click="authorizationDialog = false">关闭</el-button>
        <el-button type="primary" @click="confirmAuthorization">模拟回填授权元数据</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ml-8 {
  margin-left: 8px;
}

.store-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.tab-badge {
  margin-left: 4px;
}

.text-success {
  color: var(--el-color-success);
}

.text-danger {
  color: var(--el-color-danger);
}

.text-warning {
  color: var(--el-color-warning);
}
</style>
