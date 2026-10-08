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
const selectedScripts = ref([])
const durationSec = ref(15)
const submitting = ref(false)

const activePlan = computed(() => plans.value.find((p) => p.id === activePlanId.value) || null)
const scripts = computed(() => activePlan.value?.content_json?.scripts || [])

const scriptFields = [
  { key: 'script_title', label: '脚本标题' },
  { key: 'hook', label: '开头钩子' },
  { key: 'storyboard', label: '镜头分镜' },
  { key: 'voiceover', label: '口播文案' },
  { key: 'conversion_cta', label: '转化引导' },
]

async function load() {
  loading.value = true
  try {
    const data = await creativeApi.list(props.productId, { plan_type: 'video_script' })
    plans.value = data.items
    if (!activePlanId.value && plans.value.length) {
      activePlanId.value = plans.value[0].id
    }
    selectedScripts.value = scripts.value.map((_, i) => i)
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    const plan = await creativeApi.generateVideoScripts(props.productId)
    ElMessage.success(`视频脚本已生成（${plan.script_count} 条）`)
    await load()
    activePlanId.value = plan.id
    selectedScripts.value = (plan.content_json?.scripts || []).map((_, i) => i)
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
  ElMessage.success('脚本已保存')
  await load()
}

async function setStatus(plan, status) {
  await creativeApi.updatePlan(props.productId, plan.id, { status })
  const labels = { draft: '草稿', selected: '选中', archived: '归档' }
  ElMessage.success(`脚本已标记为「${labels[status]}」`)
  await load()
  emit('changed')
}

async function removePlan(plan) {
  try {
    await ElMessageBox.confirm(`确认删除脚本「${plan.title}」吗？`, '删除脚本', { type: 'warning' })
  } catch {
    return
  }
  await creativeApi.removePlan(props.productId, plan.id)
  ElMessage.success('脚本已删除')
  activePlanId.value = null
  await load()
  emit('changed')
}

async function submitGeneration() {
  if (!activePlan.value) return
  if (!selectedScripts.value.length) {
    ElMessage.warning('请至少选择一条脚本')
    return
  }
  submitting.value = true
  try {
    const job = await creativeApi.generateVideos(props.productId, activePlan.value.id, {
      script_indexes: selectedScripts.value,
      duration_sec: durationSec.value,
      usage_scene: '短视频',
    })
    ElMessage.success(`视频生成任务已入队（任务 #${job.id}），请到「任务」标签页查看进度`)
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
        生成视频脚本
      </el-button>
      <el-button v-permission="['admin', 'operator']" :icon="'Check'" :disabled="!activePlan"
                 @click="savePlan">
        保存脚本编辑
      </el-button>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <el-empty v-if="!plans.length" description="尚未生成视频脚本，点击上方按钮生成 3 条脚本"
              :image-size="90" />

    <el-row v-else :gutter="14">
      <el-col :xs="24" :lg="7">
        <el-card shadow="never">
          <template #header>
            <span class="section-title" style="margin: 0">脚本列表（{{ plans.length }}）</span>
          </template>
          <div class="plan-list">
            <div v-for="plan in plans" :key="plan.id" class="plan-item"
                 :class="{ 'is-active': plan.id === activePlanId }" @click="activePlanId = plan.id">
              <div class="plan-item-head">
                <span class="plan-title">{{ plan.title }}</span>
                <StatusTag :value="plan.status" />
              </div>
              <div class="text-small text-muted">
                脚本 {{ plan.content_json?.scripts?.length || 0 }} 条 ·
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

      <el-col :xs="24" :lg="17">
        <el-card v-if="activePlan" shadow="never">
          <template #header>
            <div class="card-head">
              <span class="section-title" style="margin: 0">脚本内容（可编辑）</span>
              <StatusTag :value="activePlan.status" />
            </div>
          </template>

          <el-form label-width="90px">
            <el-form-item label="脚本标题">
              <el-input v-model="activePlan.title" />
            </el-form-item>
            <el-form-item label="整体理由">
              <el-input v-model="activePlan.rationale_text" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>

          <el-divider content-position="left">
            脚本详情（每条需包含 开头钩子 / 镜头分镜 / 口播文案 / 转化引导）
          </el-divider>

          <div v-for="(script, index) in scripts" :key="index" class="script-block">
            <el-checkbox v-model="selectedScripts" :value="index" :label="index">
              <span class="script-index">脚本 {{ index + 1 }}</span>
            </el-checkbox>
            <el-form label-width="90px" size="small" class="mt-8">
              <el-form-item v-for="field in scriptFields" :key="field.key" :label="field.label">
                <el-input v-model="script[field.key]" type="textarea"
                          :rows="field.key === 'storyboard' ? 4 : 2" />
              </el-form-item>
            </el-form>
          </div>

          <el-divider content-position="left">提交视频生成任务</el-divider>
          <el-form label-width="120px">
            <el-form-item label="已选脚本">
              <span>{{ selectedScripts.length }} / {{ scripts.length }}</span>
            </el-form-item>
            <el-form-item label="目标时长">
              <el-input-number v-model="durationSec" :min="5" :max="120" :step="5" />
              <span class="text-small text-muted ml-8">秒</span>
            </el-form-item>
            <el-form-item>
              <el-button v-permission="['admin', 'operator']" type="primary" :icon="'VideoCamera'"
                         :loading="submitting" @click="submitGeneration">
                提交视频生成任务（异步）
              </el-button>
              <span class="text-small text-muted ml-8">
                第一版产出视频海报帧与时长字段，便于演示任务链路
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

.script-block {
  border: 1px solid var(--mp-border);
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fafbfc;
}

.script-index {
  font-weight: 600;
}

.ml-8 {
  margin-left: 8px;
}
</style>
