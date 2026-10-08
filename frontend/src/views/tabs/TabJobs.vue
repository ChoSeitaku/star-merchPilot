<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { jobApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import StatusTag from '@/components/StatusTag.vue'
import JobEventsTimeline from '@/components/JobEventsTimeline.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const auth = useAuthStore()

const loading = ref(false)
const jobs = ref([])
const worker = ref(null)
const filterKind = ref('')
const filterStatus = ref('')

const detailDialog = ref(false)
const currentJob = ref(null)
const events = ref([])
const eventsLoading = ref(false)
const autoRefresh = ref(true)
const selectedJobIds = ref([])

let timer = null

const hasActiveJob = computed(() =>
  jobs.value.some((j) => ['pending', 'running'].includes(j.job_status)),
)

async function load({ silent = false } = {}) {
  if (!silent) loading.value = true
  try {
    const data = await jobApi.productJobs(props.productId, {
      job_kind: filterKind.value || undefined,
      job_status: filterStatus.value || undefined,
      limit: 100,
    })
    jobs.value = data.items
    worker.value = data.worker
  } finally {
    loading.value = false
  }
}

/** 只在标签页处于激活状态时轮询，切走即停止，避免无谓请求 */
function startPolling() {
  stopPolling()
  if (!autoRefresh.value) return
  timer = setInterval(() => {
    if (hasActiveJob.value || jobs.value.length === 0) {
      load({ silent: true }).then(() => {
        if (detailDialog.value && currentJob.value) {
          loadEvents(currentJob.value.id, { silent: true })
        }
      })
    }
  }, 3000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function loadEvents(jobId, { silent = false } = {}) {
  if (!silent) eventsLoading.value = true
  try {
    events.value = (await jobApi.events(props.productId, jobId)).items
  } finally {
    eventsLoading.value = false
  }
}

async function openDetail(job) {
  currentJob.value = job
  detailDialog.value = true
  await loadEvents(job.id)
}

async function retry(job) {
  await jobApi.retry(props.productId, job.id)
  ElMessage.success('任务已重新入队')
  await load({ silent: true })
  if (currentJob.value?.id === job.id) await loadEvents(job.id)
  emit('changed')
}

async function cancel(job) {
  try {
    await ElMessageBox.confirm(`确认取消任务 #${job.id} 吗？`, '取消任务', { type: 'warning' })
  } catch {
    return
  }
  try {
    await jobApi.cancel(props.productId, job.id)
    ElMessage.success('任务已取消')
  } catch {
    // 冲突提示已在拦截器处理
  }
  await load({ silent: true })
  if (currentJob.value?.id === job.id) await loadEvents(job.id)
  emit('changed')
}

async function simulateFailure(job) {
  try {
    await ElMessageBox.confirm(
      `将任务 #${job.id} 标记为「下次执行必失败」，用于演示失败 → 自动重试 → 终态失败的事件链路。确认继续？`,
      '演示失败路径',
      { type: 'warning' },
    )
  } catch {
    return
  }
  await jobApi.simulateFailure(props.productId, job.id, { reason: '演示：人工注入的失败' })
  ElMessage.success('已标记，任务下次执行将按失败路径处理')
  await load()
}

async function sweepTimeouts() {
  const result = await jobApi.sweepTimeouts()
  ElMessage.success(result.message)
  await load()
}

async function batchRetry() {
  if (!selectedJobIds.value.length) {
    ElMessage.warning('请先勾选要重试的任务')
    return
  }
  const targets = jobs.value.filter(
    (j) => selectedJobIds.value.includes(j.id) && ['failed', 'timeout', 'cancelled'].includes(j.job_status),
  )
  if (!targets.length) {
    ElMessage.warning('勾选的任务中没有可重试的任务（仅失败/超时/已取消可重试）')
    return
  }
  for (const job of targets) {
    await jobApi.retry(props.productId, job.id)
  }
  ElMessage.success(`已重新入队 ${targets.length} 个任务`)
  selectedJobIds.value = []
  await load()
  emit('changed')
}

onMounted(async () => {
  await load()
  if (props.active) startPolling()
})

watch(
  () => props.active,
  (isActive) => {
    if (isActive) {
      load({ silent: true })
      startPolling()
    } else {
      stopPolling()
    }
  },
)

watch(autoRefresh, () => {
  if (props.active) startPolling()
})

onBeforeUnmount(stopPolling)
</script>

<template>
  <div>
    <div class="toolbar mb-12">
      <el-select v-model="filterKind" placeholder="全部类型" clearable style="width: 130px"
                 @change="load()">
        <el-option label="图片任务" value="image" />
        <el-option label="视频任务" value="video" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 130px"
                 @change="load()">
        <el-option label="待执行" value="pending" />
        <el-option label="执行中" value="running" />
        <el-option label="已成功" value="succeeded" />
        <el-option label="已失败" value="failed" />
        <el-option label="已取消" value="cancelled" />
        <el-option label="已超时" value="timeout" />
      </el-select>
      <el-button :icon="'Refresh'" @click="load()">刷新</el-button>
      <el-button v-permission="['admin', 'operator']" :icon="'RefreshRight'"
                 @click="batchRetry">批量重试</el-button>
      <el-button v-permission="['admin']" :icon="'Timer'" @click="sweepTimeouts">
        扫描超时任务
      </el-button>
      <el-checkbox v-model="autoRefresh" class="ml-auto">自动刷新（3 秒）</el-checkbox>
    </div>

    <el-alert v-if="worker" type="info" :closable="false" class="mb-12">
      <template #title>
        后台工作进程：{{ worker.worker_id }}
        <el-tag :type="worker.running ? 'success' : 'danger'" size="small" effect="plain"
                class="ml-8">{{ worker.running ? '运行中' : '未运行' }}</el-tag>
        <span class="ml-8">执行中任务：{{ worker.inflight_jobs?.length || 0 }}</span>
        <span class="ml-8">轮询次数：{{ worker.loop_count }}</span>
        <span v-if="worker.last_error" class="ml-8" style="color:#f56c6c">
          最近异常：{{ worker.last_error }}
        </span>
      </template>
    </el-alert>

    <el-table v-loading="loading" :data="jobs" border
              empty-text="暂无生成任务，可在「主图」或「视频」标签页提交生成任务"
              @selection-change="(rows) => (selectedJobIds = rows.map((r) => r.id))">
      <el-table-column type="selection" width="46" />
      <el-table-column prop="id" label="任务 ID" width="90" align="center">
        <template #default="{ row }">
          <el-link type="primary" @click="openDetail(row)">#{{ row.id }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.job_kind === 'image' ? 'primary' : 'warning'" effect="plain">
            {{ row.job_kind === 'image' ? '图片' : '视频' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><StatusTag :value="row.job_status" /></template>
      </el-table-column>
      <el-table-column label="尝试次数" width="100" align="center">
        <template #default="{ row }">{{ row.attempts }} / {{ row.max_attempts }}</template>
      </el-table-column>
      <el-table-column label="开始时间" width="165">
        <template #default="{ row }">
          <span class="text-small">{{ formatDateTime(row.started_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="结束时间" width="165">
        <template #default="{ row }">
          <span class="text-small">{{ formatDateTime(row.finished_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="产出素材" width="90" align="center">
        <template #default="{ row }">{{ row.result_json?.asset_count ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="失败原因 / 结果" min-width="230">
        <template #default="{ row }">
          <span v-if="row.error_message" class="text-small" style="color:#f56c6c">
            {{ row.error_message }}
          </span>
          <span v-else-if="row.result_json?.summary" class="text-small text-muted">
            {{ row.result_json.summary }}
          </span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDetail(row)">事件</el-button>
          <el-button v-permission="['admin', 'operator']" size="small" text type="success"
                     :disabled="!['failed', 'timeout', 'cancelled'].includes(row.job_status)"
                     @click="retry(row)">重试</el-button>
          <el-button v-permission="['admin', 'operator']" size="small" text type="danger"
                     :disabled="!['pending', 'running'].includes(row.job_status)"
                     @click="cancel(row)">取消</el-button>
          <el-button v-if="auth.isAdmin" size="small" text
                     :disabled="row.job_status !== 'pending'"
                     @click="simulateFailure(row)">演示失败</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 任务详情与事件时间线 -->
    <el-dialog v-model="detailDialog" :title="`任务 #${currentJob?.id} 详情`" width="760px">
      <template v-if="currentJob">
        <el-descriptions :column="2" border class="mb-12">
          <el-descriptions-item label="类型">
            {{ currentJob.job_kind === 'image' ? '图片生成' : '视频生成' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag :value="currentJob.job_status" />
          </el-descriptions-item>
          <el-descriptions-item label="尝试次数">
            {{ currentJob.attempts }} / {{ currentJob.max_attempts }}
          </el-descriptions-item>
          <el-descriptions-item label="执行者">{{ currentJob.locked_by || '—' }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">
            {{ formatDateTime(currentJob.started_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="结束时间">
            {{ formatDateTime(currentJob.finished_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="下次执行">
            {{ formatDateTime(currentJob.next_run_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="锁定时间">
            {{ formatDateTime(currentJob.locked_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="入队参数" :span="2">
            <span class="text-mono">{{ JSON.stringify(currentJob.params_json) }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentJob.error_message" label="失败原因" :span="2">
            <span style="color:#f56c6c">{{ currentJob.error_message }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentJob.result_json?.summary" label="执行结果" :span="2">
            {{ currentJob.result_json.summary }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="section-title">事件时间线</div>
        <JobEventsTimeline :events="events" :loading="eventsLoading" />
      </template>

      <template #footer>
        <el-button @click="detailDialog = false">关闭</el-button>
        <el-button v-permission="['admin', 'operator']" type="success"
                   :disabled="!currentJob || !['failed', 'timeout', 'cancelled'].includes(currentJob.job_status)"
                   @click="retry(currentJob)">重试</el-button>
        <el-button v-permission="['admin', 'operator']" type="danger"
                   :disabled="!currentJob || !['pending', 'running'].includes(currentJob.job_status)"
                   @click="cancel(currentJob)">取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ml-auto {
  margin-left: auto;
}

.ml-8 {
  margin-left: 8px;
}
</style>
