<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadTemplate, performanceApi, reviewApi } from '@/api'
import AiBlock from '@/components/AiBlock.vue'
import { formatDate, formatDateTime, formatMoney, formatNumber, formatPercent } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const loading = ref(false)
const generating = ref(false)
const records = ref([])
const aggregate = ref({})
const reports = ref([])
const latestReport = ref(null)

const activeTab = ref('performance')

// 手工录入
const recordDialog = ref(false)
const submitting = ref(false)
const recordForm = reactive({
  period_start: '',
  period_end: '',
  impressions: 0,
  clicks: 0,
  conversions: 0,
  spend: 0,
  revenue: 0,
  ctr: null,
  conversion_rate: null,
  roi: null,
  notes: '',
})

// 导入
const importFile = ref(null)
const importPreview = ref(null)
const importResult = ref(null)
const importing = ref(false)
const confirming = ref(false)

// 生成报告
const reportDialog = ref(false)
const reportForm = reactive({ period_start: '', period_end: '', remark: '' })

const derivedPreview = computed(() => {
  const { impressions, clicks, conversions, spend, revenue } = recordForm
  return {
    ctr: impressions ? ((clicks / impressions) * 100).toFixed(4) : '0.0000',
    conversion_rate: clicks ? ((conversions / clicks) * 100).toFixed(4) : '0.0000',
    roi: spend ? (revenue / spend).toFixed(4) : '0.0000',
  }
})

async function load() {
  loading.value = true
  try {
    const [perf, reportList, latest] = await Promise.all([
      performanceApi.list(props.productId),
      reviewApi.list(props.productId),
      reviewApi.latest(props.productId),
    ])
    records.value = perf.items
    aggregate.value = perf.aggregate || {}
    reports.value = reportList.items
    latestReport.value = latest.item
  } finally {
    loading.value = false
  }
}

function openRecord() {
  const today = new Date()
  const weekAgo = new Date(today.getTime() - 6 * 864e5)
  const iso = (d) => d.toISOString().slice(0, 10)
  Object.assign(recordForm, {
    period_start: iso(weekAgo),
    period_end: iso(today),
    impressions: 0,
    clicks: 0,
    conversions: 0,
    spend: 0,
    revenue: 0,
    ctr: null,
    conversion_rate: null,
    roi: null,
    notes: '',
  })
  recordDialog.value = true
}

async function submitRecord() {
  submitting.value = true
  try {
    await performanceApi.create(props.productId, { ...recordForm })
    ElMessage.success('经营数据已录入，派生指标已自动计算')
    recordDialog.value = false
    await load()
    emit('changed')
  } finally {
    submitting.value = false
  }
}

// ---------------- 导入 ----------------
function onFileChange(uploadFile) {
  importFile.value = uploadFile.raw
  importPreview.value = null
  importResult.value = null
}

async function previewImport() {
  if (!importFile.value) {
    ElMessage.warning('请先选择 xlsx 文件')
    return
  }
  const formData = new FormData()
  formData.append('file', importFile.value)
  importing.value = true
  try {
    importPreview.value = await performanceApi.importPreview(props.productId, formData)
    ElMessage.success(
      `校验完成：共 ${importPreview.value.total_rows} 行，` +
        `${importPreview.value.valid_rows} 行可导入，${importPreview.value.error_rows} 行有问题`,
    )
  } finally {
    importing.value = false
  }
}

async function confirmImport() {
  confirming.value = true
  try {
    importResult.value = await performanceApi.importConfirm(
      props.productId,
      importPreview.value.import_id,
    )
    ElMessage.success(importResult.value.message)
    await load()
    emit('changed')
  } finally {
    confirming.value = false
  }
}

async function getTemplate() {
  await downloadTemplate('performance-records')
  ElMessage.success('模板下载已开始')
}

// ---------------- 复盘报告 ----------------
function openReport() {
  const today = new Date()
  const monthAgo = new Date(today.getTime() - 27 * 864e5)
  const iso = (d) => d.toISOString().slice(0, 10)
  Object.assign(reportForm, {
    period_start: iso(monthAgo),
    period_end: iso(today),
    remark: '',
  })
  reportDialog.value = true
}

async function generateReport() {
  generating.value = true
  try {
    const report = await reviewApi.generate(props.productId, { ...reportForm })
    ElMessage.success(`复盘报告已生成（基于 ${report.based_on_record_count} 条经营数据）`)
    if (report.closed_loop_note) ElMessage.info(report.closed_loop_note)
    reportDialog.value = false
    await load()
    activeTab.value = 'report'
    emit('changed')
  } finally {
    generating.value = false
  }
}

function reportFieldText(report, key) {
  return report?.[key] || ''
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar mb-12">
      <el-button v-permission="['admin', 'operator']" type="primary" :icon="'Plus'"
                 @click="openRecord">
        录入经营数据
      </el-button>
      <el-button v-permission="['admin', 'operator']" :icon="'Upload'" @click="activeTab = 'import'">
        批量导入
      </el-button>
      <el-button v-permission="['admin', 'operator']" type="success" :icon="'MagicStick'"
                 :disabled="!records.length" @click="openReport">
        生成复盘报告
      </el-button>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <!-- 汇总指标 -->
    <el-row :gutter="12" class="mb-12">
      <el-col v-for="item in [
        { label: '曝光量', value: formatNumber(aggregate.impressions) },
        { label: '点击量', value: formatNumber(aggregate.clicks) },
        { label: '点击率', value: formatPercent(aggregate.ctr) },
        { label: '成交量', value: formatNumber(aggregate.conversions) },
        { label: '转化率', value: formatPercent(aggregate.conversion_rate) },
        { label: '花费', value: formatMoney(aggregate.spend) },
        { label: '成交金额', value: formatMoney(aggregate.revenue) },
        { label: 'ROI', value: (aggregate.roi || 0).toFixed ? Number(aggregate.roi || 0).toFixed(2) : '—' },
      ]" :key="item.label" :xs="12" :sm="8" :md="3">
        <el-card shadow="never" body-style="padding:12px 14px">
          <div class="stat-value stat-small">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab">
      <!-- 经营数据 -->
      <el-tab-pane :label="`经营数据（${records.length}）`" name="performance">
        <el-table :data="records" border empty-text="暂无经营数据，可手工录入或批量导入"
                  max-height="460">
          <el-table-column label="周期" width="190">
            <template #default="{ row }">
              {{ formatDate(row.period_start) }} ~ {{ formatDate(row.period_end) }}
            </template>
          </el-table-column>
          <el-table-column label="曝光" width="100" align="right">
            <template #default="{ row }">{{ formatNumber(row.impressions) }}</template>
          </el-table-column>
          <el-table-column label="点击" width="90" align="right">
            <template #default="{ row }">{{ formatNumber(row.clicks) }}</template>
          </el-table-column>
          <el-table-column label="CTR" width="90" align="right">
            <template #default="{ row }">{{ formatPercent(row.ctr) }}</template>
          </el-table-column>
          <el-table-column label="成交" width="80" align="right">
            <template #default="{ row }">{{ row.conversions }}</template>
          </el-table-column>
          <el-table-column label="转化率" width="90" align="right">
            <template #default="{ row }">{{ formatPercent(row.conversion_rate) }}</template>
          </el-table-column>
          <el-table-column label="花费" width="110" align="right">
            <template #default="{ row }">{{ formatMoney(row.spend) }}</template>
          </el-table-column>
          <el-table-column label="成交金额" width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.revenue) }}</template>
          </el-table-column>
          <el-table-column label="ROI" width="80" align="right">
            <template #default="{ row }">
              <el-tag :type="row.roi >= 2 ? 'success' : row.roi >= 1.5 ? 'warning' : 'danger'"
                      size="small" effect="plain">
                {{ Number(row.roi).toFixed(2) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="180" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>

      <!-- 批量导入 -->
      <el-tab-pane label="批量导入" name="import">
        <div class="compliance-note mb-12">
          导入流程：下载模板 → 填写 → 上传预览（逐行校验并提示错误行）→ 确认导入。
          导入允许部分成功：校验通过的行正常写入，出错的行会被跳过并给出原因。
        </div>

        <el-form label-width="110px" class="form-narrow">
          <el-form-item label="xlsx 文件">
            <el-upload :auto-upload="false" :limit="1" accept=".xlsx"
                       :on-change="onFileChange" :show-file-list="true">
              <el-button :icon="'FolderOpened'">选择文件</el-button>
            </el-upload>
          </el-form-item>
          <el-form-item>
            <el-button :icon="'Download'" @click="getTemplate">下载经营数据模板</el-button>
            <el-button type="primary" :icon="'Upload'" :loading="importing" @click="previewImport">
              上传并预览校验
            </el-button>
            <el-button type="success" :icon="'Check'" :loading="confirming"
                       :disabled="!importPreview?.can_confirm" @click="confirmImport">
              确认导入
            </el-button>
          </el-form-item>
        </el-form>

        <template v-if="importPreview">
          <el-divider content-position="left">校验预览</el-divider>
          <el-row :gutter="12" class="mb-12">
            <el-col :span="6">
              <div class="mini-stat">
                <div class="mini-value">{{ importPreview.total_rows }}</div>
                <div class="mini-label">总行数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="mini-stat is-success">
                <div class="mini-value">{{ importPreview.valid_rows }}</div>
                <div class="mini-label">可导入</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="mini-stat" :class="{ 'is-danger': importPreview.error_rows > 0 }">
                <div class="mini-value">{{ importPreview.error_rows }}</div>
                <div class="mini-label">错误行</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="mini-stat">
                <div class="mini-value">{{ importPreview.can_confirm ? '可导入' : '不可导入' }}</div>
                <div class="mini-label">结论</div>
              </div>
            </el-col>
          </el-row>

          <el-table v-if="importPreview.invalid_rows?.length" :data="importPreview.invalid_rows"
                    border size="small" max-height="240">
            <el-table-column prop="row_no" label="行号" width="80" align="center" />
            <el-table-column label="错误原因" min-width="400">
              <template #default="{ row }">
                <el-tag v-for="(err, i) in row.errors" :key="i" type="danger" size="small"
                        effect="plain" class="error-tag">{{ err }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <template v-if="importResult">
          <el-divider content-position="left">导入结果</el-divider>
          <el-result :icon="importResult.failed_rows === 0 ? 'success' : 'warning'"
                     :title="importResult.message" />
        </template>
      </el-tab-pane>

      <!-- 复盘报告 -->
      <el-tab-pane :label="`复盘报告（${reports.length}）`" name="report">
        <el-empty v-if="!reports.length" description="尚未生成复盘报告，请先录入经营数据后生成"
                  :image-size="90" />

        <template v-else>
          <el-collapse v-model="activeTab" accordion>
            <el-collapse-item v-for="report in reports" :key="report.id" :name="report.id">
              <template #title>
                <div class="report-title">
                  <span>
                    复盘报告 #{{ report.id }} ·
                    {{ formatDate(report.period_start) }} ~ {{ formatDate(report.period_end) }}
                  </span>
                  <span class="text-small text-muted">{{ formatDateTime(report.created_at) }}</span>
                </div>
              </template>

              <AiBlock label="周期摘要" :value="reportFieldText(report, 'summary_text')"
                       :ordered="false" />
              <AiBlock label="核心洞察" :value="report.insights_json"
                       title-key="insight_title" content-key="insight_detail" />
              <AiBlock label="下一步动作" :value="report.next_actions_json"
                       title-key="action_title" content-key="action_detail" />

              <el-alert type="success" :closable="false" class="mt-12"
                        title="闭环提示：报告中「下一步动作」会在下一次生成商品诊断时自动作为输入，点击「诊断」标签页的「生成诊断」即可开启下一轮优化。" />
            </el-collapse-item>
          </el-collapse>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 录入经营数据 -->
    <el-dialog v-model="recordDialog" title="录入经营数据" width="620px">
      <el-form :model="recordForm" label-width="110px">
        <el-form-item label="统计周期">
          <el-date-picker v-model="recordForm.period_start" type="date" value-format="YYYY-MM-DD"
                          placeholder="开始日期" style="width: 46%" />
          <span class="mx-8">~</span>
          <el-date-picker v-model="recordForm.period_end" type="date" value-format="YYYY-MM-DD"
                          placeholder="结束日期" style="width: 46%" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="曝光量" label-width="70px">
              <el-input-number v-model="recordForm.impressions" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="点击量" label-width="70px">
              <el-input-number v-model="recordForm.clicks" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="成交量" label-width="70px">
              <el-input-number v-model="recordForm.conversions" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="花费金额" label-width="90px">
              <el-input-number v-model="recordForm.spend" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成交金额" label-width="90px">
              <el-input-number v-model="recordForm.revenue" :min="0" :precision="2"
                               style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-alert type="info" :closable="false" class="mb-12">
          <template #title>
            派生指标将自动计算：CTR = {{ derivedPreview.ctr }}% ·
            转化率 = {{ derivedPreview.conversion_rate }}% · ROI = {{ derivedPreview.roi }}
            （也可以在下方的字段里手工覆盖）
          </template>
        </el-alert>

        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="CTR(%)" label-width="70px">
              <el-input-number v-model="recordForm.ctr" :min="0" :precision="4" :controls="false"
                               placeholder="自动" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="转化率(%)" label-width="80px">
              <el-input-number v-model="recordForm.conversion_rate" :min="0" :precision="4"
                               :controls="false" placeholder="自动" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="ROI" label-width="60px">
              <el-input-number v-model="recordForm.roi" :min="0" :precision="4" :controls="false"
                               placeholder="自动" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="recordForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRecord">保存</el-button>
      </template>
    </el-dialog>

    <!-- 生成复盘报告 -->
    <el-dialog v-model="reportDialog" title="生成复盘报告" width="520px">
      <el-alert type="info" :closable="false" class="mb-12"
                title="报告将基于所选周期内的经营数据生成，输出周期摘要、核心洞察与下一步动作" />
      <el-form :model="reportForm" label-width="110px">
        <el-form-item label="复盘周期">
          <el-date-picker v-model="reportForm.period_start" type="date" value-format="YYYY-MM-DD"
                          placeholder="开始日期" style="width: 46%" />
          <span class="mx-8">~</span>
          <el-date-picker v-model="reportForm.period_end" type="date" value-format="YYYY-MM-DD"
                          placeholder="结束日期" style="width: 46%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="reportForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="generateReport">生成报告</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-narrow {
  max-width: 680px;
}

.stat-small {
  font-size: 17px;
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

.report-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
}

.mx-8 {
  margin: 0 4px;
}
</style>
