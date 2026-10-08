<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { linkApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime, formatNumber } from '@/utils/format'

const props = defineProps({
  productId: { type: Number, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const loading = ref(false)
const generating = ref(false)
const links = ref([])
const suggestions = ref([])

const createDialog = ref(false)
const creating = ref(false)
const createForm = reactive({
  link_name: '',
  target_url: '',
  scene_text: '',
  utmText: '',
})

const clicksDialog = ref(false)
const clicks = ref([])
const clicksLoading = ref(false)
const clicksLink = ref(null)

async function load() {
  loading.value = true
  try {
    links.value = (await linkApi.list(props.productId)).items
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    const result = await linkApi.generate(props.productId)
    suggestions.value = result.items
    ElMessage.success(`已生成 ${result.total} 条推广链接建议，确认后可创建`)
  } finally {
    generating.value = false
  }
}

function openCreate(suggestion = null) {
  Object.assign(createForm, {
    link_name: suggestion?.link_name || '',
    target_url: suggestion?.target_url || '',
    scene_text: suggestion?.scene_text || '',
    utmText: suggestion ? JSON.stringify(suggestion.utm || {}, null, 0) : '',
  })
  createDialog.value = true
}

async function submitCreate() {
  if (!createForm.link_name || !createForm.target_url) {
    ElMessage.warning('链接名称与目标地址为必填项')
    return
  }
  let utm = {}
  if (createForm.utmText.trim()) {
    try {
      utm = JSON.parse(createForm.utmText)
    } catch {
      ElMessage.error('UTM 参数不是合法的 JSON')
      return
    }
  }

  creating.value = true
  try {
    await linkApi.create(props.productId, {
      link_name: createForm.link_name,
      target_url: createForm.target_url,
      scene_text: createForm.scene_text,
      utm_json: utm,
      status: 'active',
    })
    ElMessage.success('推广链接已创建，访问追踪地址会自动记录点击')
    createDialog.value = false
    await load()
    emit('changed')
  } finally {
    creating.value = false
  }
}

async function toggleStatus(link) {
  const next = link.status === 'active' ? 'inactive' : 'active'
  await linkApi.update(props.productId, link.id, { status: next })
  ElMessage.success(next === 'active' ? '链接已启用' : '链接已停用')
  await load()
}

async function showClicks(link) {
  clicksLink.value = link
  clicksDialog.value = true
  clicksLoading.value = true
  try {
    const data = await linkApi.clicks(props.productId, link.id)
    clicks.value = data.items
  } finally {
    clicksLoading.value = false
  }
}

async function openTrackUrl(link) {
  const url = `${window.location.origin}${link.track_url}`
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success(`追踪地址已复制：${url}`)
  } catch {
    ElMessage.info(`追踪地址：${url}`)
  }
}

async function visitTrack(link) {
  // 打开短链，后端会记录点击并 302 跳转
  window.open(link.track_url, '_blank')
  setTimeout(load, 800)
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar mb-12">
      <el-button v-permission="['admin', 'operator']" type="primary" :icon="'MagicStick'"
                 :loading="generating" @click="generate">
        生成推广链接建议
      </el-button>
      <el-button v-permission="['admin', 'operator']" :icon="'Plus'" @click="openCreate()">
        手工创建链接
      </el-button>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <el-alert type="info" :closable="false" class="mb-12">
      <template #title>
        追踪地址形如 <span class="text-mono">/api/v1/r/{tracking_code}</span>，
        无需登录即可访问：访问时会记录点击（IP、User-Agent、时间）并 302 跳转到目标地址，
        用于区分不同渠道的引流效果。
      </template>
    </el-alert>

    <!-- 建议列表 -->
    <el-card v-if="suggestions.length" shadow="never" class="mb-12">
      <template #header>
        <span class="section-title" style="margin: 0">推广链接建议（{{ suggestions.length }}）</span>
      </template>
      <el-table :data="suggestions" border size="small">
        <el-table-column prop="link_name" label="建议名称" min-width="200" />
        <el-table-column prop="scene_text" label="使用场景" min-width="220" />
        <el-table-column prop="target_url" label="目标地址" min-width="220" show-overflow-tooltip />
        <el-table-column label="UTM 参数" min-width="240">
          <template #default="{ row }">
            <span class="text-mono text-small">{{ JSON.stringify(row.utm) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="['admin', 'operator']" size="small" text type="primary"
                       @click="openCreate(row)">创建</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 已创建链接 -->
    <el-card shadow="never">
      <template #header>
        <span class="section-title" style="margin: 0">已创建链接（{{ links.length }}）</span>
      </template>
      <el-table :data="links" border empty-text="暂无推广链接">
        <el-table-column prop="link_name" label="链接名称" min-width="180" />
        <el-table-column prop="scene_text" label="使用场景" min-width="180" show-overflow-tooltip />
        <el-table-column label="追踪码" width="130">
          <template #default="{ row }">
            <span class="text-mono">{{ row.tracking_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="点击统计" width="180" align="right">
          <template #default="{ row }">
            <el-tag type="primary" size="small" effect="plain">
              {{ formatNumber(row.click_count) }} 次
            </el-tag>
            <div class="text-small text-muted">
              记录 {{ row.click_records }} 条 · 最近 {{ formatDateTime(row.last_clicked_at) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><StatusTag :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="操作" width="270" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openTrackUrl(row)">复制地址</el-button>
            <el-button size="small" text type="success" @click="visitTrack(row)">模拟访问</el-button>
            <el-button size="small" text @click="showClicks(row)">点击明细</el-button>
            <el-button v-permission="['admin', 'operator']" size="small" text
                       :type="row.status === 'active' ? 'warning' : 'success'"
                       @click="toggleStatus(row)">
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建链接 -->
    <el-dialog v-model="createDialog" title="创建推广链接" width="560px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="链接名称" required>
          <el-input v-model="createForm.link_name" />
        </el-form-item>
        <el-form-item label="目标地址" required>
          <el-input v-model="createForm.target_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="使用场景">
          <el-input v-model="createForm.scene_text" />
        </el-form-item>
        <el-form-item label="UTM 参数">
          <el-input v-model="createForm.utmText" type="textarea" :rows="3"
                    placeholder='{"utm_source":"merchpilot","utm_medium":"link"}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 点击明细 -->
    <el-dialog v-model="clicksDialog" :title="`点击明细 · ${clicksLink?.link_name}`" width="700px">
      <el-descriptions :column="2" border class="mb-12">
        <el-descriptions-item label="追踪码">
          <span class="text-mono">{{ clicksLink?.tracking_code }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="累计点击">{{ clicksLink?.click_count }}</el-descriptions-item>
        <el-descriptions-item label="目标地址" :span="2">
          {{ clicksLink?.target_url }}
        </el-descriptions-item>
        <el-descriptions-item label="带参链接" :span="2">
          <span class="text-mono text-small">{{ clicksLink?.full_track_url }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-table v-loading="clicksLoading" :data="clicks" border max-height="360" empty-text="暂无点击记录">
        <el-table-column label="点击时间" width="180">
          <template #default="{ row }">
            <span class="text-small">{{ formatDateTime(row.clicked_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="client_ip" label="来源 IP" width="150">
          <template #default="{ row }"><span class="text-mono">{{ row.client_ip }}</span></template>
        </el-table-column>
        <el-table-column prop="user_agent" label="User-Agent" min-width="260" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>
