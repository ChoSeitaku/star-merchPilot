<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { storeApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { PLATFORM_OPTIONS, formatDateTime, platformLabel } from '@/utils/format'

const router = useRouter()

const loading = ref(false)
const stores = ref([])
const keyword = ref('')
const platform = ref('')

const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const form = reactive({
  store_name: '',
  platform: 'taobao',
  external_store_id: '',
  owner_name: '',
  remark: '',
})

const rules = {
  store_name: [{ required: true, message: '请输入店铺名称', trigger: 'blur' }],
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
}

async function load() {
  loading.value = true
  try {
    const data = await storeApi.list({
      keyword: keyword.value || undefined,
      platform: platform.value || undefined,
    })
    stores.value = data.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, {
    store_name: '',
    platform: 'taobao',
    external_store_id: '',
    owner_name: '',
    remark: '',
  })
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await storeApi.create({ ...form })
    ElMessage.success('店铺创建成功')
    dialogVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">店铺列表</h1>
        <p class="page-subtitle">管理店铺信息、平台归属与库存预警概览</p>
      </div>
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索店铺名 / 负责人"
          clearable
          style="width: 200px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-select v-model="platform" placeholder="全部平台" clearable style="width: 140px"
                   @change="load">
          <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                     :value="item.value" />
        </el-select>
        <el-button :icon="'Search'" @click="load">查询</el-button>
        <el-button v-permission="['admin']" type="primary" :icon="'Plus'" @click="openCreate">
          创建店铺
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="stores" stripe empty-text="暂无店铺数据">
        <el-table-column prop="store_name" label="店铺名称" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="router.push(`/stores/${row.id}`)">
              {{ row.store_name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="平台" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="external_store_id" label="外部店铺 ID" width="150">
          <template #default="{ row }">
            <span class="text-mono">{{ row.external_store_id || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="product_count" label="商品数量" width="100" align="right" />
        <el-table-column label="库存预警" width="110" align="right">
          <template #default="{ row }">
            <el-tag v-if="row.low_stock_count > 0" type="danger" size="small" effect="plain">
              {{ row.low_stock_count }}
            </el-tag>
            <span v-else class="text-muted">0</span>
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="负责人" width="120">
          <template #default="{ row }">{{ row.owner_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span class="text-small">{{ formatDateTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="router.push(`/stores/${row.id}`)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="创建店铺" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="店铺名称" prop="store_name">
          <el-input v-model="form.store_name" placeholder="例如：星航优选旗舰店" />
        </el-form-item>
        <el-form-item label="所属平台" prop="platform">
          <el-select v-model="form.platform" style="width: 100%">
            <el-option v-for="item in PLATFORM_OPTIONS" :key="item.value" :label="item.label"
                       :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="外部店铺 ID">
          <el-input v-model="form.external_store_id" placeholder="平台侧的店铺 ID（可留空）" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="form.owner_name" placeholder="店铺负责人" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
