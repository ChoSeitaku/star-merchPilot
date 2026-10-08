<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { productApi, storeApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import {
  PLATFORM_OPTIONS,
  formatDateTime,
  formatMoney,
  formatPercent,
  platformLabel,
} from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const products = ref([])
const total = ref(0)
const stores = ref([])

const filters = reactive({
  keyword: '',
  store_id: route.query.store_id ? Number(route.query.store_id) : null,
  platform: route.query.platform || '',
  status: '',
  page: 1,
  size: 20,
})

const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const form = reactive({
  store_id: null,
  name: '',
  platform: 'taobao',
  category: '',
  price: 0,
  cost: 0,
  target_audience: '',
  selling_points: '',
  product_url: '',
  status: 'draft',
})

const rules = {
  store_id: [{ required: true, message: '请选择所属店铺', trigger: 'change' }],
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
}

async function load() {
  loading.value = true
  try {
    const data = await productApi.list({
      keyword: filters.keyword || undefined,
      store_id: filters.store_id || undefined,
      platform: filters.platform || undefined,
      status: filters.status || undefined,
      offset: (filters.page - 1) * filters.size,
      limit: filters.size,
    })
    products.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.store_id = null
  filters.platform = ''
  filters.status = ''
  filters.page = 1
  load()
}

async function openCreate() {
  if (!stores.value.length) {
    stores.value = (await storeApi.list()).items
  }
  Object.assign(form, {
    store_id: stores.value[0]?.id || null,
    name: '',
    platform: 'taobao',
    category: '',
    price: 0,
    cost: 0,
    target_audience: '',
    selling_points: '',
    product_url: '',
    status: 'draft',
  })
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const created = await productApi.create({ ...form })
    ElMessage.success('商品创建成功，正在进入详情页')
    dialogVisible.value = false
    router.push(`/products/${created.id}`)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  stores.value = (await storeApi.list()).items
  await load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">商品池</h1>
        <p class="page-subtitle">共 {{ total }} 个商品，点击进入详情页体验 9 个标签页的完整闭环</p>
      </div>
      <div class="toolbar">
        <el-input v-model="filters.keyword" placeholder="搜索商品名 / 类目" clearable
                  style="width: 190px" @keyup.enter="load" @clear="load" />
        <el-select v-model="filters.store_id" placeholder="全部店铺" clearable style="width: 170px"
                   @change="load">
          <el-option v-for="s in stores" :key="s.id" :label="s.store_name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.platform" placeholder="全部平台" clearable style="width: 130px"
                   @change="load">
          <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                     :value="item.value" />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px"
                   @change="load">
          <el-option label="草稿" value="draft" />
          <el-option label="在售" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
        <el-button :icon="'Refresh'" @click="resetFilters">重置</el-button>
        <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Plus'"
                   @click="openCreate">
          创建商品
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="products" stripe empty-text="暂无商品">
        <el-table-column prop="name" label="商品名称" min-width="220">
          <template #default="{ row }">
            <el-link type="primary" @click="router.push(`/products/${row.id}`)">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="平台" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类目" width="130" />
        <el-table-column label="价格 / 成本" width="150" align="right">
          <template #default="{ row }">
            <div>{{ formatMoney(row.price) }}</div>
            <div class="text-small text-muted">成本 {{ formatMoney(row.cost) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="毛利率" width="100" align="right">
          <template #default="{ row }">
            <el-tag :type="row.margin_rate >= 40 ? 'success' : row.margin_rate >= 20 ? 'warning' : 'danger'"
                    size="small" effect="plain">
              {{ formatPercent(row.margin_rate, 1) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="store_name" label="店铺归属" width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><StatusTag :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="最近诊断" width="160">
          <template #default="{ row }">
            <span class="text-small">{{ formatDateTime(row.last_diagnosis_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近复盘" width="160">
          <template #default="{ row }">
            <span class="text-small">{{ formatDateTime(row.last_review_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="router.push(`/products/${row.id}`)">
              运营
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="mt-12"
        @current-change="load"
        @size-change="load"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" title="创建商品" width="620px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="所属店铺" prop="store_id">
          <el-select v-model="form.store_id" style="width: 100%" placeholder="请选择店铺">
            <el-option v-for="s in stores" :key="s.id" :label="s.store_name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：轻量通勤双肩包 15.6 寸电脑仓" />
        </el-form-item>
        <el-form-item label="平台" prop="platform">
          <el-select v-model="form.platform" style="width: 100%">
            <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                       :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="form.category" placeholder="例如：箱包/双肩包" />
        </el-form-item>
        <el-form-item label="售价 / 成本">
          <el-input-number v-model="form.price" :min="0" :precision="2" :step="10" />
          <span class="mx-8">/</span>
          <el-input-number v-model="form.cost" :min="0" :precision="2" :step="10" />
        </el-form-item>
        <el-form-item label="目标人群">
          <el-input v-model="form.target_audience" placeholder="例如：22-35 岁通勤上班族" />
        </el-form-item>
        <el-form-item label="核心卖点">
          <el-input v-model="form.selling_points" type="textarea" :rows="2"
                    placeholder="多条用英文逗号分隔，例如：轻量,防泼水,大容量" />
        </el-form-item>
        <el-form-item label="商品链接">
          <el-input v-model="form.product_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="商品状态">
          <el-radio-group v-model="form.status">
            <el-radio value="draft">草稿</el-radio>
            <el-radio value="active">在售</el-radio>
            <el-radio value="inactive">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">创建并进入详情</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mx-8 {
  margin: 0 8px;
}
</style>
