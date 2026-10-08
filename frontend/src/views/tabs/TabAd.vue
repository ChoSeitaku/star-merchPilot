<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import StatusTag from '@/components/StatusTag.vue'
import AiBlock from '@/components/AiBlock.vue'
import { formatDateTime, formatMoney } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const auth = useAuthStore()

const COMPLIANCE_NOTE =
  '本模块只生成投放建议与实验计划，不自动创建广告计划、不自动扣费、不直接修改预算；' +
  '所有投放动作需由具备权限的人员确认后在平台侧手动执行。'

const loading = ref(false)
const generating = ref(false)
const recommendations = ref([])
const experiments = ref([])
const allowedTransitions = ref({})
const activeTab = ref('recommendation')

const genForm = reactive({ objective: '转化', daily_budget: null })

const confirmDialog = ref(false)
const confirmTarget = ref(null)
const confirmForm = reactive({ confirm_status: 'confirmed', confirm_remark: '' })

const experimentDialog = ref(false)
const experimentForm = reactive({
  experiment_name: '',
  budget_amount: null,
  related_asset_id: null,
  related_link_id: null,
})

const statusDialog = ref(false)
const statusTarget = ref(null)
const nextStatus = ref('')

const TRANSITION_LABELS = {
  draft: '草稿',
  confirmed: '已确认',
  running: '执行中',
  finished: '已结束',
  cancelled: '已取消',
}

async function load() {
  loading.value = true
  try {
    const [recs, exps] = await Promise.all([
      adApi.recommendations(props.productId),
      adApi.experiments(props.productId),
    ])
    recommendations.value = recs.items
    experiments.value = exps.items
    allowedTransitions.value = exps.allowed_transitions || {}
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    await adApi.generateRecommendation(props.productId, {
      objective: genForm.objective,
      daily_budget: genForm.daily_budget,
    })
    ElMessage.success('投放建议已生成（待人工确认）')
    await load()
    activeTab.value = 'recommendation'
    emit('changed')
  } finally {
    generating.value = false
  }
}

function openConfirm(rec, status) {
  confirmTarget.value = rec
  Object.assign(confirmForm, {
    confirm_status: status,
    confirm_remark: status === 'confirmed' ? '同意本轮投放计划' : '暂不执行，需调整后再评估',
  })
  confirmDialog.value = true
}

async function submitConfirm() {
  const result = await adApi.confirmRecommendation(props.productId, confirmTarget.value.id, {
    ...confirmForm,
  })
  ElMessage.success(result.message)
  confirmDialog.value = false
  await load()
  emit('changed')
}

function openExperiment() {
  if (!recommendations.value.length) {
    ElMessage.warning('请先生成投放建议，实验计划需要基于建议创建')
    return
  }
  const rec = recommendations.value[0]
  Object.assign(experimentForm, {
    experiment_name: '素材点击效率对比实验',
    budget_amount: rec.budget_plan_json?.daily_budget || 300,
    related_asset_id: null,
    related_link_id: null,
  })
  experimentDialog.value = true
}

async function submitExperiment() {
  await adApi.generateExperiment(props.productId, { ...experimentForm })
  ElMessage.success('投放实验计划已生成（草稿状态）')
  experimentDialog.value = false
  await load()
  activeTab.value = 'experiment'
  emit('changed')
}

function openStatusDialog(experiment, status) {
  statusTarget.value = experiment
  nextStatus.value = status
  statusDialog.value = true
}

async function submitStatus() {
  await adApi.updateExperiment(props.productId, statusTarget.value.id, {
    experiment_status: nextStatus.value,
  })
  ElMessage.success(`实验状态已更新为「${TRANSITION_LABELS[nextStatus.value]}」`)
  statusDialog.value = false
  await load()
  emit('changed')
}

const pendingCount = computed(
  () => recommendations.value.filter((r) => r.confirm_status === 'pending').length,
)

async function quickConfirmAll() {
  const pending = recommendations.value.filter((r) => r.confirm_status === 'pending')
  if (!pending.length) {
    ElMessage.info('没有待确认的投放建议')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将确认 ${pending.length} 条待确认建议（操作人：${auth.displayName}）。确认后仍不会自动执行投放。`,
      '批量确认投放建议',
      { type: 'warning' },
    )
  } catch {
    return
  }
  for (const rec of pending) {
    await adApi.confirmRecommendation(props.productId, rec.id, {
      confirm_status: 'confirmed',
      confirm_remark: '批量确认',
    })
  }
  ElMessage.success(`已确认 ${pending.length} 条建议`)
  await load()
  emit('changed')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="compliance-note mb-12">{{ COMPLIANCE_NOTE }}</div>

    <div class="toolbar mb-12">
      <el-select v-model="genForm.objective" style="width: 140px">
        <el-option label="转化" value="转化" />
        <el-option label="点击" value="点击" />
        <el-option label="拉新" value="拉新" />
        <el-option label="复购" value="复购" />
      </el-select>
      <el-input-number v-model="genForm.daily_budget" :min="0" :precision="2" :step="50"
                       placeholder="日预算（可留空）" style="width: 180px" />
      <el-button v-permission="['admin', 'operator']" type="primary" :icon="'MagicStick'"
                 :loading="generating" @click="generate">
        生成投放建议
      </el-button>
      <el-button v-permission="['admin', 'operator']" :icon="'Plus'" @click="openExperiment">
        生成实验计划
      </el-button>
      <el-button v-permission="['admin', 'operator']" type="success" :icon="'Select'"
                 :disabled="!pendingCount" @click="quickConfirmAll">
        批量确认（{{ pendingCount }}）
      </el-button>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <!-- 投放建议 -->
      <el-tab-pane name="recommendation">
        <template #label>
          投放建议
          <el-badge v-if="pendingCount" :value="pendingCount" type="warning" class="tab-badge" />
        </template>

        <el-empty v-if="!recommendations.length"
                  description="尚未生成投放建议，点击上方按钮生成（包含策略摘要、目标、人群、预算、素材测试、出价、风控与下一步）"
                  :image-size="90" />

        <div v-for="rec in recommendations" :key="rec.id" class="rec-card">
          <div class="rec-head">
            <div class="rec-head-left">
              <span class="rec-title">投放建议 #{{ rec.id }}</span>
              <StatusTag :value="rec.confirm_status" />
            </div>
            <div class="rec-head-right">
              <span class="text-small text-muted">{{ formatDateTime(rec.created_at) }}</span>
              <el-button v-if="rec.confirm_status === 'pending'" v-permission="['admin', 'operator']"
                         size="small" type="success" @click="openConfirm(rec, 'confirmed')">
                确认
              </el-button>
              <el-button v-if="rec.confirm_status === 'pending'" v-permission="['admin', 'operator']"
                         size="small" type="danger" @click="openConfirm(rec, 'rejected')">
                驳回
              </el-button>
            </div>
          </div>

          <div v-if="rec.confirm_status !== 'pending'" class="confirm-info">
            由用户 #{{ rec.confirmed_by }} 于 {{ formatDateTime(rec.confirmed_at) }}
            {{ rec.confirm_status === 'confirmed' ? '确认' : '驳回' }}
            <span v-if="rec.confirm_remark">：{{ rec.confirm_remark }}</span>
          </div>

          <el-row :gutter="12">
            <el-col :xs="24" :md="12">
              <AiBlock label="策略摘要" :value="rec.summary_text" :ordered="false" />
              <AiBlock label="本轮目标" :value="rec.objective_text" :ordered="false" />
              <AiBlock label="人群建议" :value="rec.audience_segments_json"
                       title-key="segment_name"
                       content-key="description" />
              <AiBlock label="风险控制" :value="rec.risk_controls_json" />
            </el-col>
            <el-col :xs="24" :md="12">
              <div class="ai-block">
                <div class="ai-block-label">预算建议</div>
                <el-descriptions :column="2" size="small" border>
                  <el-descriptions-item label="日预算">
                    {{ formatMoney(rec.budget_plan_json?.daily_budget) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="总预算">
                    {{ formatMoney(rec.budget_plan_json?.total_budget) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="周期">
                    {{ rec.budget_plan_json?.duration_days || '—' }} 天
                  </el-descriptions-item>
                  <el-descriptions-item label="目标 CPA">
                    {{ formatMoney(rec.budget_plan_json?.target_cpa) }}
                  </el-descriptions-item>
                </el-descriptions>
                <div v-if="rec.budget_plan_json?.phase_plan?.length" class="mt-8">
                  <div v-for="(phase, i) in rec.budget_plan_json.phase_plan" :key="i"
                       class="phase-line text-small">
                    <b>{{ phase.phase }}</b> · 预算 {{ formatMoney(phase.budget) }} · {{ phase.focus }}
                  </div>
                </div>
                <div v-if="rec.budget_plan_json?.note" class="text-small text-muted mt-8">
                  {{ rec.budget_plan_json.note }}
                </div>
              </div>

              <AiBlock label="素材测试建议" :value="rec.creative_tests_json"
                       title-key="test_name" content-key="hypothesis" />

              <div class="ai-block">
                <div class="ai-block-label">出价策略</div>
                <div class="pre-wrap">
                  <div>模式：{{ rec.bid_strategy_json?.mode || '—' }}</div>
                  <div>初始出价：{{ formatMoney(rec.bid_strategy_json?.initial_bid) }}</div>
                  <div>出价上限：{{ formatMoney(rec.bid_strategy_json?.bid_ceiling) }}</div>
                  <div v-if="rec.bid_strategy_json?.adjust_rule">
                    调整规则：{{ rec.bid_strategy_json.adjust_rule }}
                  </div>
                  <div v-if="rec.bid_strategy_json?.note" class="text-muted text-small">
                    {{ rec.bid_strategy_json.note }}
                  </div>
                </div>
              </div>

              <AiBlock label="下一步动作" :value="rec.next_steps_json" />
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- 投放实验 -->
      <el-tab-pane label="投放实验" name="experiment">
        <el-table :data="experiments" border empty-text="暂无投放实验计划">
          <el-table-column prop="id" label="ID" width="70" align="center" />
          <el-table-column prop="experiment_name" label="实验名称" min-width="200" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><StatusTag :value="row.experiment_status" /></template>
          </el-table-column>
          <el-table-column label="预算" width="110" align="right">
            <template #default="{ row }">{{ formatMoney(row.budget_amount) }}</template>
          </el-table-column>
          <el-table-column prop="audience_text" label="目标人群" min-width="150"
                           show-overflow-tooltip />
          <el-table-column prop="hypothesis_text" label="实验假设" min-width="220"
                           show-overflow-tooltip />
          <el-table-column prop="success_metric_text" label="成功指标" min-width="180"
                           show-overflow-tooltip />
          <el-table-column label="关联" width="130">
            <template #default="{ row }">
              <div v-if="row.related_asset_id" class="text-small">
                素材 #{{ row.related_asset_id }}
              </div>
              <div v-if="row.related_link_id" class="text-small">
                链接 #{{ row.related_link_id }}
              </div>
              <span v-if="!row.related_asset_id && !row.related_link_id" class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <template v-if="(allowedTransitions[row.experiment_status] || []).length">
                <el-button
                  v-for="status in allowedTransitions[row.experiment_status]"
                  :key="status"
                  v-permission="['admin', 'operator']"
                  size="small"
                  text
                  :type="status === 'cancelled' ? 'danger' : 'primary'"
                  @click="openStatusDialog(row, status)"
                >
                  → {{ TRANSITION_LABELS[status] }}
                </el-button>
              </template>
              <span v-else class="text-muted text-small">终态，不可变更</span>
            </template>
          </el-table-column>
        </el-table>

        <el-alert type="info" :closable="false" class="mt-12">
          <template #title>
            状态流转：草稿 → 已确认 → 执行中 → 已结束（或任意阶段取消）。
            状态变更仅记录管理意图，系统不会触发任何平台侧投放动作。
          </template>
        </el-alert>
      </el-tab-pane>
    </el-tabs>

    <!-- 确认 / 驳回 -->
    <el-dialog v-model="confirmDialog"
               :title="confirmForm.confirm_status === 'confirmed' ? '确认投放建议' : '驳回投放建议'"
               width="520px">
      <el-alert :type="confirmForm.confirm_status === 'confirmed' ? 'success' : 'warning'"
                :closable="false" class="mb-12"
                :title="confirmForm.confirm_status === 'confirmed'
                  ? '确认后仍不会自动投放：请在平台侧按建议手动创建计划与预算'
                  : '驳回后该建议不会被用于执行，可重新生成'" />
      <el-form :model="confirmForm" label-width="90px">
        <el-form-item label="确认意见">
          <el-input v-model="confirmForm.confirm_remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmDialog = false">取消</el-button>
        <el-button :type="confirmForm.confirm_status === 'confirmed' ? 'success' : 'danger'"
                   @click="submitConfirm">
          确认提交
        </el-button>
      </template>
    </el-dialog>

    <!-- 生成实验 -->
    <el-dialog v-model="experimentDialog" title="生成投放实验计划" width="540px">
      <el-form :model="experimentForm" label-width="110px">
        <el-form-item label="实验名称">
          <el-input v-model="experimentForm.experiment_name" />
        </el-form-item>
        <el-form-item label="实验预算">
          <el-input-number v-model="experimentForm.budget_amount" :min="0" :precision="2"
                           :step="50" style="width: 100%" />
        </el-form-item>
        <el-form-item label="关联素材 ID">
          <el-input-number v-model="experimentForm.related_asset_id" :min="0" style="width: 100%"
                           placeholder="留空则自动选用已通过审核的素材" />
        </el-form-item>
        <el-form-item label="关联链接 ID">
          <el-input-number v-model="experimentForm.related_link_id" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="experimentDialog = false">取消</el-button>
        <el-button type="primary" @click="submitExperiment">生成</el-button>
      </template>
    </el-dialog>

    <!-- 状态流转确认 -->
    <el-dialog v-model="statusDialog" title="更新实验状态" width="460px">
      <el-alert type="warning" :closable="false" class="mb-12"
                title="状态变更仅用于记录管理意图，不会触发任何平台侧投放动作" />
      <p>
        确认把实验「{{ statusTarget?.experiment_name }}」的状态从
        <b>{{ TRANSITION_LABELS[statusTarget?.experiment_status] }}</b>
        变更为 <b>{{ TRANSITION_LABELS[nextStatus] }}</b> 吗？
      </p>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
        <el-button type="primary" @click="submitStatus">确认变更</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rec-card {
  border: 1px solid var(--mp-border);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.rec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--mp-border);
  margin-bottom: 12px;
}

.rec-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rec-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rec-title {
  font-size: 15px;
  font-weight: 600;
}

.confirm-info {
  background: #f0f9eb;
  border-radius: 6px;
  padding: 7px 11px;
  font-size: 12.5px;
  color: #529b2e;
  margin-bottom: 12px;
}

.phase-line {
  line-height: 1.9;
}

.tab-badge {
  margin-left: 4px;
}
</style>
