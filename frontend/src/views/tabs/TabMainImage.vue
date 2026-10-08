<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { creativeApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const loading = ref(false)
const generating = ref(false)
const plans = ref([])
const activePlanId = ref(null)
const selectedDirections = ref([])
const countPerDirection = ref(1)
const submitting = ref(false)

const activePlan = computed(() => plans.value.find((p) => p.id === activePlanId.value) || null)
const directions = computed(() => activePlan.value?.content_json?.directions || [])

const directionFields = [
  { key: 'direction_title', label: '方案标题' },
  { key: 'visual_structure', label: '画面结构' },
  { key: 'core_copy', label: '核心文案' },
  { key: 'highlight_selling_point', label: '突出卖点' },
  { key: 'rationale', label: '方案理由' },
]

async function load() {
  loading.value = true
  try {
    const data = await creativeApi.list(props.productId, { plan_type: 'main_image' })
    plans.value = data.items
    if (!activePlanId.value && plans.value.length) {
      activePlanId.value = plans.value[0].id
    }
    selectedDirections.value = directions.value.map((_, i) => i)
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    const plan = await creativeApi.generateMainImages(props.productId)
    ElMessage.success(`主图方案已生成（${plan.direction_count} 个方向）`)
    await load()
    activePlanId.value = plan.id
    selectedDirections.value = (plan.content_json?.directions || []).map((_, i) => i)
    emit('changed')
  } finally {
    generating.value = false
  }
}

async function savePlan() {
  if (!activePlan.value) return
  await creativeApi.updatePlan(props.productId, activePlan.value.id, {
    title: activePlan.value.title,
    rationale_text: activePlan.value.rationale_text,
    content_json: activePlan.value.content_json,
  })
  ElMessage.success('方案已保存')
  await load()
}

async function setStatus(plan, status) {
  await creativeApi.updatePlan(props.productId, plan.id, { status })
  const labels = { draft: '草稿', selected: '选中', archived: '归档' }
  ElMessage.success(`方案已标记为「${labels[status]}」`)
  await load()
  emit('changed')
}

async function removePlan(plan) {
  try {
    await ElMessageBox.confirm(`确认删除方案「${plan.title}」吗？其下素材与任务会一并删除。`, '删除方案', {
      type: 'warning',
    })
  } catch {
    return
  }
  await creativeApi.removePlan(props.productId, plan.id)
  ElMessage.success('方案已删除')
  activePlanId.value = null
  await load()
  emit('changed')
}

async function submitGeneration() {
  if (!activePlan.value) return
  if (!selectedDirections.value.length) {
    ElMessage.warning('请至少选择一个方向')
    return
  }
  submitting.value = true
  try {
    const job = await creativeApi.generateImages(props.productId, activePlan.value.id, {
      direction_indexes: selectedDirections.value,
      count_per_direction: countPerDirection.value,
      usage_scene: '主图',
    })
    ElMessage.success(`图片生成任务已入队（任务 #${job.id}），请到「任务」标签页查看进度`)
    emit('changed')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar mb-12">
      <el-button v-permission="['admin', 'operator']" type="primary" :icon="'MagicStick'"
                 :loading="generating" @click="generate">
        生成主图方案
      </el-button>
      <el-button v-permission="['admin', 'operator']" :icon="'Check'" :disabled="!activePlan"
                 @click="savePlan">
        保存方案编辑
      </el-button>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <el-empty v-if="!plans.length" description="尚未生成主图方案，点击上方按钮生成 3 个方向"
              :image-size="90" />

    <el-row v-else :gutter="14">
      <!-- 方案列表 -->
      <el-col :xs="24" :lg="7">
        <el-card shadow="never">
          <template #header>
            <span class="section-title" style="margin: 0">方案列表（{{ plans.length }}）</span>
          </template>
          <div class="plan-list">
            <div v-for="plan in plans" :key="plan.id" class="plan-item"
                 :class="{ 'is-active': plan.id === activePlanId }" @click="activePlanId = plan.id">
              <div class="plan-item-head">
                <span class="plan-title">{{ plan.title }}</span>
                <StatusTag :value="plan.status" />
              </div>
              <div class="text-small text-muted">
                方向 {{ plan.content_json?.directions?.length || 0 }} 个 ·
                素材 {{ plan.asset_count }} · 任务 {{ plan.job_count }}
              </div>
              <div class="text-small text-muted">{{ formatDateTime(plan.created_at) }}</div>
              <div class="plan-actions" @click.stop>
                <el-button v-permission="['admin', 'operator']" size="small" text type="primary"
                           :disabled="plan.status === 'selected'"
                           @click="setStatus(plan, 'selected')">选中</el-button>
                <el-button v-permission="['admin', 'operator']" size="small" text
                           :disabled="plan.status === 'draft'"
                           @click="setStatus(plan, 'draft')">转草稿</el-button>
                <el-button v-permission="['admin', 'operator']" size="small" text
                           :disabled="plan.status === 'archived'"
                           @click="setStatus(plan, 'archived')">归档</el-button>
                <el-button v-permission="['admin', 'operator']" size="small" text type="danger"
                           @click="removePlan(plan)">删除</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 方案详情 -->
      <el-col :xs="24" :lg="17">
        <el-card v-if="activePlan" shadow="never">
          <template #header>
            <div class="card-head">
              <span class="section-title" style="margin: 0">方案内容（可编辑）</span>
              <StatusTag :value="activePlan.status" />
            </div>
          </template>

          <el-form label-width="90px">
            <el-form-item label="方案标题">
              <el-input v-model="activePlan.title" />
            </el-form-item>
            <el-form-item label="整体理由">
              <el-input v-model="activePlan.rationale_text" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>

          <el-divider content-position="left">方向详情（每个方向需包含标题 / 画面结构 / 核心文案 / 突出卖点 / 理由）</el-divider>

          <div v-for="(direction, index) in directions" :key="index" class="direction-block">
            <div class="direction-head">
              <el-checkbox v-model="selectedDirections" :value="index" :label="index">
                <span class="direction-index">方向 {{ index + 1 }}</span>
              </el-checkbox>
            </div>
            <el-form label-width="90px" size="small">
              <el-form-item v-for="field in directionFields" :key="field.key" :label="field.label">
                <el-input v-model="direction[field.key]" type="textarea" :rows="2" />
              </el-form-item>
            </el-form>
          </div>

          <el-divider content-position="left">提交图片生成任务</el-divider>
          <el-form label-width="120px">
            <el-form-item label="已选方向">
              <span>{{ selectedDirections.length }} / {{ directions.length }}</span>
              <span class="text-small text-muted ml-8">
                （未勾选的方向不会被生成）
              </span>
            </el-form-item>
            <el-form-item label="每方向生成张数">
              <el-input-number v-model="countPerDirection" :min="1" :max="4" />
            </el-form-item>
            <el-form-item>
              <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Picture'"
                         :loading="submitting" @click="submitGeneration">
                提交图片生成任务（异步）
              </el-button>
              <span class="text-small text-muted ml-8">
                任务在后台执行，不会阻塞页面；进度见「任务」标签页
              </span>
            </el-form-item>
          </el-form>
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
}

.plan-list {
  max-height: 560px;
  overflow-y: auto;
}

.plan-item {
  border: 1px solid var(--mp-border);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 9px;
  cursor: pointer;
  transition: all 0.16s;
}

.plan-item:hover {
  border-color: var(--el-color-primary);
}

.plan-item.is-active {
  border-color: var(--el-color-primary);
  background: #f0f7ff;
}

.plan-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}

.plan-title {
  font-weight: 600;
  font-size: 13.5px;
}

.plan-actions {
  margin-top: 7px;
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.direction-block {
  border: 1px solid var(--mp-border);
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fafbfc;
}

.direction-head {
  margin-bottom: 8px;
}

.direction-index {
  font-weight: 600;
}

.ml-8 {
  margin-left: 8px;
}
</style>
