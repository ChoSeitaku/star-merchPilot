<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadTemplate, importApi, productApi, storeApi } from '@/api'

const activeTab = ref('products')

const cards = [
  {
    key: 'products',
    title: '商品导入',
    desc: '批量导入商品主档信息（店铺、名称、平台、类目、价格等）',
    template: 'products',
    needProduct: false,
  },
  {
    key: 'sku-inventory',
    title: 'SKU 库存导入',
    desc: '为已有商品批量导入 SKU 与期初库存，并写入库存流水',
    template: 'sku-inventory',
    needProduct: false,
  },
  {
    key: 'platform-mappings',
    title: '平台字段映射导入',
    desc: '建立系统商品与各平台商品 ID / SKU ID 的映射关系',
    template: 'platform-mappings',
    needProduct: false,
  },
  {
    key: 'performance-records',
    title: '经营数据导入',
    desc: '按周期导入曝光、点击、成交、花费与成交金额，用于生成复盘报告',
    template: 'performance-records',
    needProduct: true,
    apiType: 'performance',
  },
]

const state = reactive({})
cards.forEach((card) => {
  state[card.key] = {
    file: null,
    uploading: false,
    confirming: false,
    preview: null,
    result: null,
    productId: null,
  }
})

const products = ref([])
const stores = ref([])

const productOptions = computed(() =>
  products.value.map((p) => ({ label: `${p.name}（${p.store_name || '未知店铺'}）`, value: p.id })),
)

function onFileChange(card, uploadFile) {
  state[card.key].file = uploadFile.raw
  state[card.key].preview = null
  state[card.key].result = null
}

function onFileRemove(card) {
  state[card.key].file = null
}

async function preview(card) {
  const item = state[card.key]
  if (!item.file) {
    ElMessage.warning('请先选择要导入的 xlsx 文件')
    return
  }
  if (card.needProduct && !item.productId) {
    ElMessage.warning('经营数据导入需要先选择商品')
    return
  }

  const formData = new FormData()
  formData.append('file', item.file)

  item.uploading = true
  try {
    const apiType = card.apiType || card.key
    const params = card.needProduct ? { product_id: item.productId } : undefined
    item.preview = await importApi.preview(apiType, formData, params)
    item.result = null
    ElMessage.success(
      `校验完成：共 ${item.preview.total_rows} 行，${item.preview.valid_rows} 行可导入，` +
        `${item.preview.error_rows} 行存在问题`,
    )
  } finally {
    item.uploading = false
  }
}

async function confirm(card) {
  const item = state[card.key]
  if (!item.preview?.import_id) {
    ElMessage.warning('请先完成上传预览')
    return
  }

  item.confirming = true
  try {
    const apiType = card.apiType || card.key
    const params = { import_id: item.preview.import_id }
    if (card.needProduct) params.product_id = item.productId
    item.result = await importApi.confirm(apiType, params)
    ElMessage.success(item.result.message)
  } finally {
    item.confirming = false
  }
}

async function getTemplate(card) {
  await downloadTemplate(card.template)
  ElMessage.success('模板下载已开始')
}

onMounted(async () => {
  const [productData, storeData] = await Promise.all([
    productApi.list({ limit: 300 }),
    storeApi.list(),
  ])
  products.value = productData.items
  stores.value = storeData.items
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">导入中心</h1>
        <p class="page-subtitle">
          先下载模板填写 → 上传预览（校验并提示错误行）→ 确认导入。导入允许部分成功：
          校验通过的行正常写入，出错的行会被跳过并给出原因。
        </p>
      </div>
    </div>

    <el-alert type="info" :closable="false" class="mb-12">
      <template #title>
        导入规则：标有 * 的列为必填；SKU 编码等可能以 0 开头的字段请把单元格格式设为「文本」；
        日期请使用 YYYY-MM-DD 格式。系统会先校验再落库，确认阶段不会重复上传文件。
      </template>
    </el-alert>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane v-for="card in cards" :key="card.key" :label="card.title" :name="card.key">
        <div class="tab-body">
          <div class="tab-desc">
            <div class="tab-title">{{ card.title }}</div>
            <div class="text-muted text-small">{{ card.desc }}</div>
          </div>

          <el-form label-width="110px" class="import-form">
            <el-form-item v-if="card.needProduct" label="目标商品">
              <el-select v-model="state[card.key].productId" filterable placeholder="请选择商品"
                         style="width: 100%">
                <el-option v-for="opt in productOptions" :key="opt.value" :label="opt.label"
                           :value="opt.value" />
              </el-select>
            </el-form-item>

            <el-form-item label="xlsx 文件">
              <el-upload
                :auto-upload="false"
                :limit="1"
                accept=".xlsx"
                :show-file-list="true"
                :on-change="(file) => onFileChange(card, file)"
                :on-remove="() => onFileRemove(card)"
              >
                <el-button :icon="'FolderOpened'">选择文件</el-button>
                <template #tip>
                  <div class="text-small text-muted">
                    请使用系统模板填写，文件名建议英文；单次最多 2000 行。
                  </div>
                </template>
              </el-upload>
            </el-form-item>

            <el-form-item>
              <el-button :icon="'Download'" @click="getTemplate(card)">下载模板</el-button>
              <el-button type="primary" :icon="'Upload'" :loading="state[card.key].uploading"
                         @click="preview(card)">
                上传并预览校验
              </el-button>
              <el-button type="success" :icon="'Check'" :loading="state[card.key].confirming"
                         :disabled="!state[card.key].preview?.can_confirm"
                         @click="confirm(card)">
                确认导入
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 预览结果 -->
          <template v-if="state[card.key].preview">
            <el-divider content-position="left">校验预览</el-divider>

            <el-row :gutter="12" class="mb-12">
              <el-col :span="6">
                <div class="mini-stat">
                  <div class="mini-value">{{ state[card.key].preview.total_rows }}</div>
                  <div class="mini-label">总行数</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="mini-stat is-success">
                  <div class="mini-value">{{ state[card.key].preview.valid_rows }}</div>
                  <div class="mini-label">可导入</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="mini-stat" :class="{ 'is-danger': state[card.key].preview.error_rows > 0 }">
                  <div class="mini-value">{{ state[card.key].preview.error_rows }}</div>
                  <div class="mini-label">错误行</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="mini-stat">
                  <div class="mini-value">
                    {{ state[card.key].preview.can_confirm ? '可以导入' : '不可导入' }}
                  </div>
                  <div class="mini-label">结论</div>
                </div>
              </el-col>
            </el-row>

            <el-alert v-if="state[card.key].preview.hint" type="info" :closable="false"
                      :title="state[card.key].preview.hint" class="mb-12" />

            <el-table v-if="state[card.key].preview.invalid_rows?.length"
                      :data="state[card.key].preview.invalid_rows" border size="small"
                      max-height="260" class="mb-12">
              <el-table-column prop="row_no" label="行号" width="80" align="center" />
              <el-table-column label="错误原因" min-width="400">
                <template #default="{ row }">
                  <el-tag v-for="(err, i) in row.errors" :key="i" type="danger" size="small"
                          effect="plain" class="error-tag">
                    {{ err }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>

            <div v-if="state[card.key].preview.sample_rows?.length">
              <div class="section-title">样例行（前 {{ state[card.key].preview.sample_rows.length }} 条）</div>
              <el-table :data="state[card.key].preview.sample_rows" border size="small"
                        max-height="240">
                <el-table-column
                  v-for="key in Object.keys(state[card.key].preview.sample_rows[0])"
                  :key="key" :prop="key" :label="key" min-width="130" show-overflow-tooltip
                />
              </el-table>
            </div>
          </template>

          <!-- 导入结果 -->
          <template v-if="state[card.key].result">
            <el-divider content-position="left">导入结果</el-divider>
            <el-result
              :icon="state[card.key].result.failed_rows === 0 ? 'success' : 'warning'"
              :title="state[card.key].result.message"
            >
              <template #sub-title>
                <div class="result-stats">
                  总行数 {{ state[card.key].result.total_rows }} ·
                  成功 {{ state[card.key].result.success_rows }} ·
                  失败 {{ state[card.key].result.failed_rows }}
                </div>
              </template>
            </el-result>

            <el-table v-if="state[card.key].result.errors?.length"
                      :data="state[card.key].result.errors" border size="small" max-height="240">
              <el-table-column prop="row_no" label="行号" width="80" align="center" />
              <el-table-column label="失败原因" min-width="400">
                <template #default="{ row }">
                  <el-tag v-for="(err, i) in row.errors" :key="i" type="danger" size="small"
                          effect="plain" class="error-tag">
                    {{ err }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.tab-body {
  padding: 4px 2px;
}

.tab-desc {
  margin-bottom: 16px;
}

.tab-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.import-form {
  max-width: 720px;
}

.mini-stat {
  background: #fafbfc;
  border: 1px solid var(--mp-border);
  border-radius: 6px;
  padding: 10px 12px;
  text-align: center;
}

.mini-stat.is-success {
  border-color: #b3e19d;
  background: #f0f9eb;
}

.mini-stat.is-danger {
  border-color: #fab6b6;
  background: #fef0f0;
}

.mini-value {
  font-size: 19px;
  font-weight: 600;
}

.mini-label {
  font-size: 12px;
  color: var(--mp-text-muted);
  margin-top: 2px;
}

.error-tag {
  margin: 2px 4px 2px 0;
}

.result-stats {
  font-size: 13px;
  color: #606266;
}
</style>
