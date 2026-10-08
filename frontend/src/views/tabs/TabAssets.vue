<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { assetApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const loading = ref(false)
const syncing = ref(false)
const assets = ref([])
const reviewSummary = ref({})

const filterType = ref('')
const filterStatus = ref('')

const selectedIds = ref([])
const batchForm = reactive({
  review_status: '',
  usage_scene: '',
  score: null,
  tagsText: '',
  remark: '',
  version_no: null,
})

const editDialog = ref(false)
const editing = ref(null)
const editForm = reactive({
  review_status: 'pending',
  usage_scene: '',
  score: null,
  tagsText: '',
  remark: '',
  version_no: 1,
})

const imageAssets = computed(() => assets.value.filter((a) => a.asset_type === 'image'))
const videoAssets = computed(() => assets.value.filter((a) => a.asset_type === 'video'))

async function load() {
  loading.value = true
  try {
    const data = await assetApi.list(props.productId, {
      asset_type: filterType.value || undefined,
      review_status: filterStatus.value || undefined,
    })
    assets.value = data.items
    reviewSummary.value = data.review_summary || {}
  } finally {
    loading.value = false
  }
}

async function sync() {
  syncing.value = true
  try {
    const result = await assetApi.sync(props.productId)
    ElMessage.success(result.message)
    await load()
    emit('changed')
  } finally {
    syncing.value = false
  }
}

function tagsToText(tags) {
  return (tags || []).join(', ')
}

function textToTags(text) {
  return String(text || '')
    .split(/[,，]/)
    .map((t) => t.trim())
    .filter(Boolean)
}

async function applyBatch() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要更新的素材')
    return
  }
  const payload = { asset_ids: selectedIds.value }
  if (batchForm.review_status) payload.review_status = batchForm.review_status
  if (batchForm.usage_scene) payload.usage_scene = batchForm.usage_scene
  if (batchForm.score !== null && batchForm.score !== undefined) payload.score = batchForm.score
  if (batchForm.tagsText) payload.tags_json = textToTags(batchForm.tagsText)
  if (batchForm.remark) payload.remark = batchForm.remark
  if (batchForm.version_no) payload.version_no = batchForm.version_no

  if (Object.keys(payload).length === 1) {
    ElMessage.warning('请至少填写一项要更新的内容')
    return
  }

  const result = await assetApi.updateReview(props.productId, payload)
  ElMessage.success(result.message)
  selectedIds.value = []
  Object.assign(batchForm, {
    review_status: '',
    usage_scene: '',
    score: null,
    tagsText: '',
    remark: '',
    version_no: null,
  })
  await load()
  emit('changed')
}

function openEdit(asset) {
  editing.value = asset
  Object.assign(editForm, {
    review_status: asset.review_status,
    usage_scene: asset.usage_scene,
    score: asset.score,
    tagsText: tagsToText(asset.tags_json),
    remark: asset.remark,
    version_no: asset.version_no,
  })
  editDialog.value = true
}

async function submitEdit() {
  await assetApi.updateReview(props.productId, {
    asset_ids: [editing.value.id],
    review_status: editForm.review_status,
    usage_scene: editForm.usage_scene,
    score: editForm.score,
    tags_json: textToTags(editForm.tagsText),
    remark: editForm.remark,
    version_no: editForm.version_no,
  })
  ElMessage.success('素材信息已更新')
  editDialog.value = false
  await load()
  emit('changed')
}

async function quickReview(asset, status) {
  const labels = { approved: '通过', rejected: '驳回', pending: '退回待审' }
  await assetApi.updateReview(props.productId, {
    asset_ids: [asset.id],
    review_status: status,
  })
  ElMessage.success(`素材 #${asset.id} 已${labels[status]}`)
  await load()
  emit('changed')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar mb-12">
      <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 130px"
                 @change="load">
        <el-option label="图片素材" value="image" />
        <el-option label="视频素材" value="video" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="全部审核状态" clearable style="width: 150px"
                 @change="load">
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
      </el-select>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
      <el-button v-permission="['admin', 'operator']" type="primary" :icon="'RefreshRight'"
                 :loading="syncing" @click="sync">
        同步素材
      </el-button>
    </div>

    <el-row :gutter="12" class="mb-12">
      <el-col v-for="item in [
        { key: 'pending', label: '待审核', type: 'warning' },
        { key: 'approved', label: '已通过', type: 'success' },
        { key: 'rejected', label: '已驳回', type: 'danger' },
      ]" :key="item.key" :span="6">
        <el-card shadow="never" body-style="padding:12px 14px">
          <div class="stat-value" :style="{ color: `var(--el-color-${item.type})` }">
            {{ reviewSummary[item.key] || 0 }}
          </div>
          <div class="stat-label">{{ item.label }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" body-style="padding:12px 14px">
          <div class="stat-value">{{ assets.length }}</div>
          <div class="stat-label">当前筛选结果</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 批量审核 -->
    <el-card shadow="never" class="mb-12">
      <template #header>
        <div class="card-head">
          <span class="section-title" style="margin: 0">
            批量审核（已选 {{ selectedIds.length }} 个）
          </span>
          <el-button size="small" text @click="selectedIds = []">清空选择</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="batchForm">
        <el-form-item label="审核状态">
          <el-select v-model="batchForm.review_status" clearable placeholder="不变更" style="width: 130px">
            <el-option label="待审核" value="pending" />
            <el-option label="通过" value="approved" />
            <el-option label="驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="使用场景">
          <el-input v-model="batchForm.usage_scene" placeholder="如：主图 / 短视频" style="width: 150px" />
        </el-form-item>
        <el-form-item label="评分">
          <el-input-number v-model="batchForm.score" :min="0" :max="5" :step="0.5" />
        </el-form-item>
        <el-form-item label="版本号">
          <el-input-number v-model="batchForm.version_no" :min="1" style="width: 110px" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="batchForm.tagsText" placeholder="多个用逗号分隔" style="width: 180px" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.remark" style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button v-permission="['admin', 'operator']" type="primary" @click="applyBatch">
            应用到已选素材
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-empty v-if="!assets.length" description="素材库为空，请先在「主图」或「视频」标签页提交生成任务"
              :image-size="90" />

    <el-checkbox-group v-else v-model="selectedIds">
      <el-row :gutter="12">
        <el-col v-for="asset in assets" :key="asset.id" :xs="12" :sm="8" :md="6" :lg="4">
          <el-card shadow="hover" body-style="padding:10px" class="asset-card">
            <div class="asset-check">
              <el-checkbox :value="asset.id" />
            </div>
            <el-image
              :src="asset.asset_url"
              :class="['asset-thumb', { 'is-video': asset.asset_type === 'video' }]"
              fit="contain"
              :preview-src-list="[asset.asset_url]"
              preview-teleported
            />
            <div class="asset-info">
              <div class="asset-line">
                <el-tag size="small" :type="asset.asset_type === 'image' ? 'primary' : 'warning'"
                        effect="plain">
                  {{ asset.asset_type === 'image' ? '图片' : '视频' }}
                </el-tag>
                <StatusTag :value="asset.review_status" />
              </div>
              <div class="text-small text-muted asset-meta">
                #{{ asset.id }} · v{{ asset.version_no }}
                <span v-if="asset.duration_sec"> · {{ asset.duration_sec }}s</span>
                <span v-if="asset.width"> · {{ asset.width }}×{{ asset.height }}</span>
              </div>
              <div v-if="asset.score !== null" class="text-small">
                评分：<el-rate :model-value="asset.score" disabled size="small" allow-half />
              </div>
              <div class="text-small text-muted asset-scene">{{ asset.usage_scene || '未设置场景' }}</div>
              <div v-if="asset.tags_json?.length" class="asset-tags">
                <el-tag v-for="tag in asset.tags_json" :key="tag" size="small" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
              <div v-if="asset.remark" class="text-small text-muted asset-remark">
                {{ asset.remark }}
              </div>
              <div class="text-small text-muted">{{ formatDateTime(asset.created_at) }}</div>
            </div>

            <div class="asset-actions">
              <el-button v-permission="['admin', 'operator']" size="small" text type="success"
                         @click="quickReview(asset, 'approved')">通过</el-button>
              <el-button v-permission="['admin', 'operator']" size="small" text type="danger"
                         @click="quickReview(asset, 'rejected')">驳回</el-button>
              <el-button v-permission="['admin', 'operator']" size="small" text type="primary"
                         @click="openEdit(asset)">编辑</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-checkbox-group>

    <el-dialog v-model="editDialog" :title="`编辑素材 #${editing?.id}`" width="560px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="审核状态">
          <el-select v-model="editForm.review_status" style="width: 100%">
            <el-option label="待审核" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="使用场景">
          <el-input v-model="editForm.usage_scene" placeholder="如：主图 / 短视频 / 详情页" />
        </el-form-item>
        <el-form-item label="版本号">
          <el-input-number v-model="editForm.version_no" :min="1" />
        </el-form-item>
        <el-form-item label="评分">
          <el-rate v-model="editForm.score" allow-half show-score />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editForm.tagsText" placeholder="多个用逗号分隔" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.asset-card {
  position: relative;
  margin-bottom: 12px;
}

.asset-check {
  position: absolute;
  top: 6px;
  left: 8px;
  z-index: 2;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 4px;
  padding: 0 4px;
}

.asset-info {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.asset-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.asset-meta,
.asset-scene,
.asset-remark {
  line-height: 1.5;
}

.asset-remark {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.asset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.asset-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  border-top: 1px dashed var(--mp-border);
  padding-top: 5px;
}

.asset-actions :deep(.el-button) {
  margin-left: 0;
  padding: 4px 6px;
}
</style>
