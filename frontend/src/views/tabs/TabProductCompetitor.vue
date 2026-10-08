<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { competitorApi, productApi, storeApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useProductStore } from '@/stores/product'
import StatusTag from '@/components/StatusTag.vue'
import {
  PLATFORM_OPTIONS,
  formatDateTime,
  formatMoney,
  platformLabel,
} from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const productStore = useProductStore()
const auth = useAuthStore()
const product = computed(() => productStore.product)
const canEdit = computed(() => auth.canEdit)

const activeSection = ref('basic')
const saving = ref(false)

// 商品基础信息
const basicForm = reactive({
  name: '',
  platform: 'other',
  category: '',
  price: 0,
  cost: 0,
  target_audience: '',
  selling_points: '',
  product_url: '',
  status: 'draft',
})

const stores = ref([])

function syncBasicForm() {
  if (!product.value) return
  Object.assign(basicForm, {
    name: product.value.name,
    platform: product.value.platform,
    category: product.value.category,
    price: product.value.price,
    cost: product.value.cost,
    target_audience: product.value.target_audience,
    selling_points: product.value.selling_points,
    product_url: product.value.product_url,
    status: product.value.status,
  })
}

async function saveBasic() {
  saving.value = true
  try {
    await productApi.update(props.productId, { ...basicForm })
    ElMessage.success('商品信息已保存')
    await productStore.refresh()
    syncBasicForm()
  } finally {
    saving.value = false
  }
}

// ---------------- 平台映射 ----------------
const mappingDialog = ref(false)
const mappingForm = reactive({
  platform: 'taobao',
  platform_product_id: '',
  platform_sku_id: '',
  mapping_status: 'mapped',
})

function openMapping() {
  Object.assign(mappingForm, {
    platform: 'taobao',
    platform_product_id: '',
    platform_sku_id: '',
    mapping_status: 'mapped',
  })
  mappingDialog.value = true
}

async function submitMapping() {
  await productApi.createMapping(props.productId, { ...mappingForm })
  ElMessage.success('平台映射已创建')
  mappingDialog.value = false
  await productStore.refresh()
}

// ---------------- SKU 与库存 ----------------
const skuDialog = ref(false)
const skuEditing = ref(null)
const skuForm = reactive({
  sku_code: '',
  sku_name: '',
  specText: '',
  price: 0,
  cost: 0,
  status: 'active',
  platform_sku_id: '',
  stock_qty: 0,
  warning_threshold: 10,
  location_text: '',
})

function openSkuDialog(sku = null) {
  skuEditing.value = sku
  if (sku) {
    Object.assign(skuForm, {
      sku_code: sku.sku_code,
      sku_name: sku.sku_name,
      specText: Object.entries(sku.spec_json || {})
        .map(([k, v]) => `${k}:${v}`)
        .join(';'),
      price: sku.price,
      cost: sku.cost,
      status: sku.status,
      platform_sku_id: sku.platform_sku_id,
      stock_qty: sku.stock_qty,
      warning_threshold: sku.warning_threshold,
      location_text: sku.location_text,
    })
  } else {
    Object.assign(skuForm, {
      sku_code: '',
      sku_name: '',
      specText: '',
      price: product.value?.price || 0,
      cost: product.value?.cost || 0,
      status: 'active',
      platform_sku_id: '',
      stock_qty: 0,
      warning_threshold: 10,
      location_text: '',
    })
  }
  skuDialog.value = true
}

function parseSpec(text) {
  const spec = {}
  String(text || '')
    .replace(/；/g, ';')
    .split(';')
    .forEach((pair) => {
      const [k, v] = pair.replace(/：/g, ':').split(':')
      if (k && k.trim()) spec[k.trim()] = (v || '').trim()
    })
  return spec
}

async function submitSku() {
  if (!skuForm.sku_code) {
    ElMessage.warning('SKU 编码为必填项')
    return
  }
  if (skuEditing.value) {
    await productApi.updateSku(props.productId, skuEditing.value.id, {
      sku_name: skuForm.sku_name,
      spec_json: parseSpec(skuForm.specText),
      price: skuForm.price,
      cost: skuForm.cost,
      status: skuForm.status,
      platform_sku_id: skuForm.platform_sku_id,
    })
    ElMessage.success('SKU 已更新')
  } else {
    await productApi.createSku(props.productId, {
      sku_code: skuForm.sku_code,
      sku_name: skuForm.sku_name,
      spec_json: parseSpec(skuForm.specText),
      price: skuForm.price,
      cost: skuForm.cost,
      status: skuForm.status,
      platform_sku_id: skuForm.platform_sku_id,
      stock_qty: skuForm.stock_qty,
      warning_threshold: skuForm.warning_threshold,
      location_text: skuForm.location_text,
    })
    ElMessage.success('SKU 已创建（含期初库存流水）')
  }
  skuDialog.value = false
  await productStore.refresh()
  emit('changed')
}

async function toggleSku(sku) {
  const next = sku.status === 'active' ? 'inactive' : 'active'
  await productApi.updateSku(props.productId, sku.id, { status: next })
  ElMessage.success(next === 'active' ? 'SKU 已启用' : 'SKU 已停用')
  await productStore.refresh()
}

// 库存调整
const inventoryDialog = ref(false)
const inventorySku = ref(null)
const inventoryForm = reactive({
  change_qty: 0,
  movement_type: 'adjust',
  reason_text: '',
  warning_threshold: null,
})

function openInventory(sku) {
  inventorySku.value = sku
  Object.assign(inventoryForm, {
    change_qty: 0,
    movement_type: 'adjust',
    reason_text: '',
    warning_threshold: sku.warning_threshold,
  })
  inventoryDialog.value = true
}

async function submitInventory() {
  if (!inventoryForm.change_qty) {
    ElMessage.warning('变动数量不能为 0')
    return
  }
  const result = await productApi.adjustInventory(props.productId, inventorySku.value.id, {
    ...inventoryForm,
  })
  ElMessage.success(result.message)
  inventoryDialog.value = false
  await productStore.refresh()
}

// 库存流水
const movementsDialog = ref(false)
const movements = ref([])
const movementsLoading = ref(false)

async function showMovements(sku) {
  movementsDialog.value = true
  movementsLoading.value = true
  try {
    movements.value = (await productApi.skuMovements(props.productId, sku.id)).items
  } finally {
    movementsLoading.value = false
  }
}

// ---------------- 竞品 ----------------
const competitors = ref([])
const competitorsLoading = ref(false)
const competitorDialog = ref(false)
const competitorEditing = ref(null)
const competitorForm = reactive({
  name: '',
  platform: 'other',
  url: '',
  price: 0,
  sales_hint: '',
  title: '',
  selling_points: '',
  review_keywords: '',
})

async function loadCompetitors() {
  competitorsLoading.value = true
  try {
    competitors.value = (await competitorApi.list(props.productId)).items
  } finally {
    competitorsLoading.value = false
  }
}

function openCompetitor(competitor = null) {
  competitorEditing.value = competitor
  Object.assign(
    competitorForm,
    competitor
      ? {
          name: competitor.name,
          platform: competitor.platform,
          url: competitor.url,
          price: competitor.price,
          sales_hint: competitor.sales_hint,
          title: competitor.title,
          selling_points: competitor.selling_points,
          review_keywords: competitor.review_keywords,
        }
      : {
          name: '',
          platform: 'other',
          url: '',
          price: 0,
          sales_hint: '',
          title: '',
          selling_points: '',
          review_keywords: '',
        },
  )
  competitorDialog.value = true
}

async function submitCompetitor() {
  if (competitorEditing.value) {
    await competitorApi.update(props.productId, competitorEditing.value.id, { ...competitorForm })
    ElMessage.success('竞品已更新')
  } else {
    await competitorApi.create(props.productId, { ...competitorForm })
    ElMessage.success('竞品已录入')
  }
  competitorDialog.value = false
  await loadCompetitors()
  emit('changed')
}

async function removeCompetitor(competitor) {
  try {
    await ElMessageBox.confirm(`确认删除竞品「${competitor.name}」吗？`, '删除竞品', {
      type: 'warning',
    })
  } catch {
    return
  }
  await competitorApi.remove(props.productId, competitor.id)
  ElMessage.success('竞品已删除')
  await loadCompetitors()
  emit('changed')
}

// 公开链接解析
const parseUrlText = ref('')
const parseTasks = ref([])
const parseRunning = ref(false)

async function loadParseTasks() {
  parseTasks.value = (await competitorApi.parseTasks(props.productId)).items
}

async function createParseTasks() {
  const urls = parseUrlText.value
    .split(/\r?\n/)
    .map((u) => u.trim())
    .filter(Boolean)
  if (!urls.length) {
    ElMessage.warning('请至少输入一个公开链接')
    return
  }
  await competitorApi.createParseTasks(props.productId, {
    urls,
    auto_create_competitors: true,
  })
  ElMessage.success(`已创建 ${urls.length} 个解析任务`)
  parseUrlText.value = ''
  await loadParseTasks()
}

async function runParseTask(task) {
  parseRunning.value = true
  try {
    const result = await competitorApi.runParseTask(props.productId, task.id)
    if (result.task_status === 'succeeded') {
      ElMessage.success(`解析成功（平台：${result.result_json?.platform || '未知'}）`)
    } else {
      ElMessage.warning(result.error_message || '解析失败')
    }
    await loadParseTasks()
    await loadCompetitors()
    emit('changed')
  } finally {
    parseRunning.value = false
  }
}

// 竞品监控
const monitorDialog = ref(false)
const monitorCompetitor = ref(null)
const monitorInterval = ref(60)

function openMonitor(competitor) {
  monitorCompetitor.value = competitor
  monitorInterval.value = 60
  monitorDialog.value = true
}

async function submitMonitor() {
  await competitorApi.createMonitor(props.productId, monitorCompetitor.value.id, {
    interval_minutes: monitorInterval.value,
  })
  ElMessage.success('竞品监控已创建')
  monitorDialog.value = false
  await loadCompetitors()
}

const snapshotsDialog = ref(false)
const snapshots = ref([])
const snapshotTitle = ref('')

async function showSnapshots(competitor) {
  snapshotsDialog.value = true
  snapshotTitle.value = competitor.name
  snapshots.value = (
    await competitorApi.snapshots(props.productId, competitor.monitor_id)
  ).items
}

async function runDueMonitors() {
  const result = await competitorApi.runDue(props.productId)
  ElMessage.success(
    result.total ? `本次运行了 ${result.total} 个到期监控，已生成快照` : '当前没有到期的监控任务',
  )
  await loadCompetitors()
  emit('changed')
}

onMounted(async () => {
  syncBasicForm()
  stores.value = (await storeApi.list()).items
  await Promise.all([loadCompetitors(), loadParseTasks()])
})

watch(
  () => product.value?.id,
  () => syncBasicForm(),
)
</script>

<template>
  <div>
    <el-tabs v-model="activeSection" type="card" class="inner-tabs">
      <!-- 基础信息 -->
      <el-tab-pane label="商品基础信息" name="basic">
        <el-form :model="basicForm" label-width="110px" class="form-narrow">
          <el-form-item label="商品名称">
            <el-input v-model="basicForm.name" :disabled="!canEdit" />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="平台">
                <el-select v-model="basicForm.platform" style="width: 100%">
                  <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                             :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="类目">
                <el-input v-model="basicForm.category" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="售价">
                <el-input-number v-model="basicForm.price" :min="0" :precision="2"
                                 style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="成本">
                <el-input-number v-model="basicForm.cost" :min="0" :precision="2"
                                 style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="目标人群">
            <el-input v-model="basicForm.target_audience" />
          </el-form-item>
          <el-form-item label="核心卖点">
            <el-input v-model="basicForm.selling_points" type="textarea" :rows="2"
                      placeholder="多条用英文逗号分隔" />
          </el-form-item>
          <el-form-item label="商品链接">
            <el-input v-model="basicForm.product_url" />
          </el-form-item>
          <el-form-item label="商品状态">
            <el-radio-group v-model="basicForm.status">
              <el-radio value="draft">草稿</el-radio>
              <el-radio value="active">在售</el-radio>
              <el-radio value="inactive">停用</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button v-permission="['admin', 'operator']" type="primary" :loading="saving"
                       @click="saveBasic">
              保存商品信息
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 平台映射 -->
      <el-tab-pane label="平台映射" name="mapping">
        <div class="toolbar mb-12">
          <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Plus'"
                     @click="openMapping">
            新增映射
          </el-button>
        </div>
        <el-table :data="product?.mappings || []" border empty-text="暂无平台映射">
          <el-table-column label="平台" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="platform_product_id" label="平台商品 ID" min-width="180">
            <template #default="{ row }"><span class="text-mono">{{ row.platform_product_id }}</span></template>
          </el-table-column>
          <el-table-column prop="platform_sku_id" label="平台 SKU ID" min-width="180">
            <template #default="{ row }"><span class="text-mono">{{ row.platform_sku_id || '—' }}</span></template>
          </el-table-column>
          <el-table-column prop="mapping_status" label="映射状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.mapping_status === 'mapped' ? 'success' : 'warning'" size="small"
                      effect="plain">{{ row.mapping_status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">
              <span class="text-small">{{ formatDateTime(row.created_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- SKU 与库存 -->
      <el-tab-pane label="SKU 与库存" name="sku">
        <div class="toolbar mb-12">
          <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Plus'"
                     @click="openSkuDialog()">
            新增 SKU
          </el-button>
          <el-button :icon="'Refresh'" @click="productStore.refresh()">刷新</el-button>
        </div>

        <el-table :data="product?.skus || []" border empty-text="暂无 SKU，请先新增">
          <el-table-column prop="sku_code" label="SKU 编码" width="150">
            <template #default="{ row }"><span class="text-mono">{{ row.sku_code }}</span></template>
          </el-table-column>
          <el-table-column prop="sku_name" label="SKU 名称" min-width="150" />
          <el-table-column label="规格" min-width="150">
            <template #default="{ row }">
              <el-tag v-for="(v, k) in row.spec_json" :key="k" size="small" effect="plain"
                      class="spec-tag">{{ k }}:{{ v }}</el-tag>
              <span v-if="!Object.keys(row.spec_json || {}).length" class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="价格 / 成本" width="130" align="right">
            <template #default="{ row }">
              <div>{{ formatMoney(row.price) }}</div>
              <div class="text-small text-muted">{{ formatMoney(row.cost) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="库存" width="140" align="right">
            <template #default="{ row }">
              <el-tag :type="row.is_low_stock ? 'danger' : 'success'" size="small" effect="plain">
                {{ row.stock_qty }}
              </el-tag>
              <div class="text-small text-muted">
                可用 {{ row.available_qty }} / 阈值 {{ row.warning_threshold }}
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="location_text" label="库位" width="110">
            <template #default="{ row }">{{ row.location_text || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }"><StatusTag :value="row.status" /></template>
          </el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <el-button v-permission="['admin', 'operator']" size="small" text type="primary"
                         @click="openInventory(row)">调库存</el-button>
              <el-button size="small" text @click="showMovements(row)">流水</el-button>
              <el-button v-permission="['admin', 'operator']" size="small" text
                         @click="openSkuDialog(row)">编辑</el-button>
              <el-button v-permission="['admin', 'operator']" size="small" text
                         :type="row.status === 'active' ? 'warning' : 'success'"
                         @click="toggleSku(row)">
                {{ row.status === 'active' ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 竞品 -->
      <el-tab-pane name="competitor">
        <template #label>
          竞品
          <el-badge v-if="competitors.length" :value="competitors.length" type="primary"
                    class="tab-badge" />
        </template>

        <div class="toolbar mb-12">
          <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Plus'"
                     @click="openCompetitor()">
            录入竞品
          </el-button>
          <el-button v-permission="['admin', 'operator']" :icon="'Refresh'"
                     @click="runDueMonitors">
            运行到期监控
          </el-button>
          <el-button :icon="'Refresh'" @click="loadCompetitors">刷新</el-button>
        </div>

        <el-table v-loading="competitorsLoading" :data="competitors" border
                  empty-text="暂无竞品，可手工录入或通过公开链接解析补充">
          <el-table-column prop="name" label="竞品名称" min-width="170" />
          <el-table-column label="平台" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="价格" width="110" align="right">
            <template #default="{ row }">{{ formatMoney(row.price) }}</template>
          </el-table-column>
          <el-table-column prop="sales_hint" label="销量提示" width="130" />
          <el-table-column prop="selling_points" label="卖点" min-width="180" show-overflow-tooltip />
          <el-table-column prop="review_keywords" label="评价关键词" min-width="150"
                           show-overflow-tooltip />
          <el-table-column label="监控" width="130">
            <template #default="{ row }">
              <el-tag v-if="row.has_monitor" :type="row.monitor_status === 'active' ? 'success' : 'info'"
                      size="small" effect="plain">
                {{ row.monitor_status === 'active' ? '监控中' : '已暂停' }}
              </el-tag>
              <span v-else class="text-muted text-small">未监控</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button v-permission="['admin', 'operator']" size="small" text type="primary"
                         @click="openCompetitor(row)">编辑</el-button>
              <el-button v-if="!row.has_monitor" v-permission="['admin', 'operator']" size="small"
                         text type="success" @click="openMonitor(row)">加监控</el-button>
              <el-button v-else size="small" text @click="showSnapshots(row)">快照</el-button>
              <el-button v-permission="['admin', 'operator']" size="small" text type="danger"
                         @click="removeCompetitor(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 公开链接解析 -->
      <el-tab-pane label="公开链接解析" name="parse">
        <div class="compliance-note mb-12">
          合规说明：公开链接解析只做有限信息提取（识别平台 + 读取链接中的公开参数），
          不抓取页面内容，不绕过登录、验证码或平台风控。价格与销量为演示占位值，
          真实数据请通过平台开放接口或用户授权获取。
        </div>

        <el-form label-width="90px" class="form-narrow">
          <el-form-item label="公开链接">
            <el-input v-model="parseUrlText" type="textarea" :rows="4"
                      placeholder="每行一个链接，例如：&#10;https://item.taobao.com/item.htm?id=100001&#10;https://item.jd.com/10023456789.html" />
          </el-form-item>
          <el-form-item>
            <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Plus'"
                       @click="createParseTasks">
              创建解析任务
            </el-button>
          </el-form-item>
        </el-form>

        <el-table :data="parseTasks" border empty-text="暂无解析任务">
          <el-table-column prop="source_url" label="源链接" min-width="280" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><StatusTag :value="row.task_status" /></template>
          </el-table-column>
          <el-table-column prop="attempts" label="尝试次数" width="90" align="center" />
          <el-table-column label="解析结果" min-width="240">
            <template #default="{ row }">
              <template v-if="row.result_json?.ok">
                <div class="text-small">
                  平台：{{ platformLabel(row.result_json.platform) }} ·
                  ID：{{ row.result_json.extracted?.platform_product_id || '—' }}
                </div>
                <div class="text-small text-muted">
                  {{ row.result_json.extracted?.title }} ·
                  {{ formatMoney(row.result_json.extracted?.price) }} ·
                  {{ row.result_json.extracted?.sales_hint }}
                </div>
              </template>
              <span v-else-if="row.error_message" class="text-small" style="color:#f56c6c">
                {{ row.error_message }}
              </span>
              <span v-else class="text-muted text-small">尚未执行</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">
              <span class="text-small">{{ formatDateTime(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button v-permission="['admin', 'operator']" size="small" text type="primary"
                         :loading="parseRunning" @click="runParseTask(row)">
                运行
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增 / 编辑映射 -->
    <el-dialog v-model="mappingDialog" title="新增平台映射" width="480px">
      <el-form :model="mappingForm" label-width="110px">
        <el-form-item label="平台">
          <el-select v-model="mappingForm.platform" style="width: 100%">
            <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                       :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="平台商品 ID">
          <el-input v-model="mappingForm.platform_product_id" />
        </el-form-item>
        <el-form-item label="平台 SKU ID">
          <el-input v-model="mappingForm.platform_sku_id" />
        </el-form-item>
        <el-form-item label="映射状态">
          <el-select v-model="mappingForm.mapping_status" style="width: 100%">
            <el-option label="mapped（已映射）" value="mapped" />
            <el-option label="unmapped（未映射）" value="unmapped" />
            <el-option label="conflict（冲突）" value="conflict" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mappingDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMapping">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增 / 编辑 SKU -->
    <el-dialog v-model="skuDialog" :title="skuEditing ? '编辑 SKU' : '新增 SKU'" width="560px">
      <el-form :model="skuForm" label-width="110px">
        <el-form-item label="SKU 编码" required>
          <el-input v-model="skuForm.sku_code" :disabled="Boolean(skuEditing)"
                    placeholder="例如：BAG-BLK-001" />
        </el-form-item>
        <el-form-item label="SKU 名称">
          <el-input v-model="skuForm.sku_name" placeholder="例如：黑色标准款" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="skuForm.specText" placeholder="颜色:黑色;尺寸:标准" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="售价">
              <el-input-number v-model="skuForm.price" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成本">
              <el-input-number v-model="skuForm.cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <template v-if="!skuEditing">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="初始库存">
                <el-input-number v-model="skuForm.stock_qty" :min="0" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="预警阈值">
                <el-input-number v-model="skuForm.warning_threshold" :min="0" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="库位">
            <el-input v-model="skuForm.location_text" placeholder="例如：A区-01-03" />
          </el-form-item>
        </template>
        <el-form-item label="平台 SKU ID">
          <el-input v-model="skuForm.platform_sku_id" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="skuForm.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="inactive">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="skuDialog = false">取消</el-button>
        <el-button type="primary" @click="submitSku">保存</el-button>
      </template>
    </el-dialog>

    <!-- 库存调整 -->
    <el-dialog v-model="inventoryDialog" title="库存调整" width="480px">
      <el-descriptions :column="1" border class="mb-12">
        <el-descriptions-item label="SKU">
          {{ inventorySku?.sku_code }} · {{ inventorySku?.sku_name }}
        </el-descriptions-item>
        <el-descriptions-item label="当前库存">
          {{ inventorySku?.stock_qty }}（可用 {{ inventorySku?.available_qty }}）
        </el-descriptions-item>
      </el-descriptions>
      <el-form :model="inventoryForm" label-width="110px">
        <el-form-item label="变动数量">
          <el-input-number v-model="inventoryForm.change_qty" style="width: 100%" />
          <div class="text-small text-muted">正数入库、负数出库</div>
        </el-form-item>
        <el-form-item label="变动类型">
          <el-select v-model="inventoryForm.movement_type" style="width: 100%">
            <el-option label="手工调整" value="adjust" />
            <el-option label="采购入库" value="purchase" />
            <el-option label="销售出库" value="sale" />
            <el-option label="退货入库" value="return" />
          </el-select>
        </el-form-item>
        <el-form-item label="预警阈值">
          <el-input-number v-model="inventoryForm.warning_threshold" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="变动原因">
          <el-input v-model="inventoryForm.reason_text" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inventoryDialog = false">取消</el-button>
        <el-button type="primary" @click="submitInventory">确认调整</el-button>
      </template>
    </el-dialog>

    <!-- 库存流水 -->
    <el-dialog v-model="movementsDialog" title="库存流水" width="720px">
      <el-table v-loading="movementsLoading" :data="movements" border max-height="420"
                empty-text="暂无流水">
        <el-table-column label="时间" width="160">
          <template #default="{ row }">
            <span class="text-small">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="movement_type" label="类型" width="100" />
        <el-table-column label="变动" width="90" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.change_qty >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ row.change_qty >= 0 ? '+' : '' }}{{ row.change_qty }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="前 → 后" width="120" align="center">
          <template #default="{ row }">{{ row.before_qty }} → {{ row.after_qty }}</template>
        </el-table-column>
        <el-table-column prop="reason_text" label="原因" min-width="200" />
      </el-table>
    </el-dialog>

    <!-- 竞品录入 -->
    <el-dialog v-model="competitorDialog" :title="competitorEditing ? '编辑竞品' : '录入竞品'"
               width="560px">
      <el-form :model="competitorForm" label-width="110px">
        <el-form-item label="竞品名称">
          <el-input v-model="competitorForm.name" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="competitorForm.platform" style="width: 100%">
            <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                       :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="链接">
          <el-input v-model="competitorForm.url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="competitorForm.price" :min="0" :precision="2"
                           style="width: 100%" />
        </el-form-item>
        <el-form-item label="销量提示">
          <el-input v-model="competitorForm.sales_hint" placeholder="例如：月销 2000+" />
        </el-form-item>
        <el-form-item label="卖点">
          <el-input v-model="competitorForm.selling_points" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="评价关键词">
          <el-input v-model="competitorForm.review_keywords" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="competitorDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCompetitor">保存</el-button>
      </template>
    </el-dialog>

    <!-- 监控设置 -->
    <el-dialog v-model="monitorDialog" title="创建竞品监控" width="420px">
      <el-form label-width="110px">
        <el-form-item label="竞品">
          <span>{{ monitorCompetitor?.name }}</span>
        </el-form-item>
        <el-form-item label="监控间隔">
          <el-input-number v-model="monitorInterval" :min="5" :max="10080" style="width: 100%" />
          <div class="text-small text-muted">单位：分钟</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="monitorDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMonitor">创建</el-button>
      </template>
    </el-dialog>

    <!-- 监控快照 -->
    <el-dialog v-model="snapshotsDialog" :title="`监控快照 · ${snapshotTitle}`" width="680px">
      <el-table :data="snapshots" border max-height="420" empty-text="暂无快照">
        <el-table-column label="采集时间" width="170">
          <template #default="{ row }">
            <span class="text-small">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="价格" width="110" align="right">
          <template #default="{ row }">{{ formatMoney(row.price) }}</template>
        </el-table-column>
        <el-table-column prop="sales_hint" label="销量提示" width="140" />
        <el-table-column prop="selling_points" label="卖点" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-narrow {
  max-width: 700px;
}

.inner-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.spec-tag {
  margin: 2px 4px 2px 0;
}

.tab-badge {
  margin-left: 4px;
}
</style>
