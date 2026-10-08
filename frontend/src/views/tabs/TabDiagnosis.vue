<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { diagnosisApi } from '@/api'
import AiBlock from '@/components/AiBlock.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const loading = ref(false)
const generating = ref(false)
const saving = ref(false)
const history = ref([])
const current = ref(null)

const FIELDS = [
  { key: 'positioning', label: '商品定位' },
  { key: 'price_band', label: '价格带分析' },
  { key: 'audience_insights', label: '目标人群洞察' },
  { key: 'pain_points', label: '用户痛点' },
  { key: 'selling_point_analysis', label: '卖点分析' },
  { key: 'risks', label: '风险点' },
  { key: 'recommendations', label: '优化建议' },
]

const form = reactive(Object.fromEntries(FIELDS.map((f) => [f.key, ''])))
const includeReviewActions = ref(true)

function syncForm() {
  FIELDS.forEach((f) => {
    form[f.key] = current.value?.[f.key] || ''
  })
}

async function load() {
  loading.value = true
  try {
    const [latest, list] = await Promise.all([
      diagnosisApi.latest(props.productId),
      diagnosisApi.list(props.productId),
    ])
    current.value = latest.item
    history.value = list.items
    syncForm()
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    current.value = await diagnosisApi.generate(props.productId, {
      source_type: 'ai_mock',
      include_review_actions: includeReviewActions.value,
    })
    syncForm()
    ElMessage.success('诊断已生成，可在下方编辑后保存')
    if (current.value.closed_loop_note) {
      ElMessage.info(current.value.closed_loop_note)
    }
    await load()
    emit('changed')
  } finally {
    generating.value = false
  }
}

async function save() {
  if (!current.value) {
    ElMessage.warning('请先生成诊断')
    return
  }
  saving.value = true
  try {
    current.value = await diagnosisApi.update(props.productId, current.value.id, { ...form })
    ElMessage.success('诊断已保存（人工编辑内容已记录来源）')
    await load()
  } finally {
    saving.value = false
  }
}

function selectHistory(item) {
  current.value = item
  syncForm()
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar mb-12">
      <el-checkbox v-model="includeReviewActions">
        将上一轮复盘结论作为输入（形成优化闭环）
      </el-checkbox>
      <el-button v-permission="['admin', 'operator']" type="primary" :icon="'MagicStick'"
                 :loading="generating" @click="generate">
        生成诊断
      </el-button>
      <el-button v-permission="['admin', 'operator']" type="success" :icon="'Check'"
                 :loading="saving" :disabled="!current" @click="save">
        保存编辑
      </el-button>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <el-alert v-if="current?.closed_loop_note" type="success" :closable="false" class="mb-12"
              :title="current.closed_loop_note" />

    <el-empty v-if="!current" description="尚未生成诊断，点击上方「生成诊断」开始" :image-size="90" />

    <el-row v-else :gutter="14">
      <!-- 诊断内容 -->
      <el-col :xs="24" :lg="18">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span class="section-title" style="margin: 0">诊断内容（可编辑）</span>
              <span class="text-small text-muted">
                来源：{{ current.source_type === 'manual_edit' ? '人工编辑' : 'AI 生成' }} ·
                更新：{{ formatDateTime(current.updated_at) }}
              </span>
            </div>
          </template>

          <div v-if="current.summary_text" class="ai-block">
            <div class="ai-block-label">摘要</div>
            <div class="pre-wrap">{{ current.summary_text }}</div>
          </div>

          <el-form label-position="top">
            <el-form-item v-for="field in FIELDS" :key="field.key" :label="field.label">
              <el-input v-model="form[field.key]" type="textarea" :rows="4" class="pre-wrap" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 历史版本 -->
      <el-col :xs="24" :lg="6">
        <el-card shadow="never">
          <template #header>
            <span class="section-title" style="margin: 0">历史诊断（{{ history.length }}）</span>
          </template>
          <el-empty v-if="!history.length" description="暂无历史" :image-size="60" />
          <div v-else class="history-list">
            <div v-for="item in history" :key="item.id" class="history-item"
                 :class="{ 'is-active': item.id === current.id }" @click="selectHistory(item)">
              <div class="history-time">{{ formatDateTime(item.created_at) }}</div>
              <div class="history-summary text-small text-muted">{{ item.summary_text || '无摘要' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.history-list {
  max-height: 520px;
  overflow-y: auto;
}

.history-item {
  padding: 9px 10px;
  border: 1px solid var(--mp-border);
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.16s;
}

.history-item:hover {
  border-color: var(--el-color-primary);
}

.history-item.is-active {
  border-color: var(--el-color-primary);
  background: #f0f7ff;
}

.history-time {
  font-size: 12.5px;
  font-weight: 500;
  margin-bottom: 3px;
}

.history-summary {
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
