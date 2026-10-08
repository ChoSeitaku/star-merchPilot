<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { userApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'

const app = useAppStore()

const activeTab = ref('model')
const loading = ref(false)
const saving = ref(false)
const editableValues = reactive({})

const users = ref([])
const userLoading = ref(false)
const userDialog = ref(false)
const userSubmitting = ref(false)
const userFormRef = ref(null)
const userForm = reactive({
  username: '',
  password: '',
  display_name: '',
  role: 'viewer',
  status: 'active',
})

const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

const modelSettings = computed(() => app.settings?.model || [])
const queueSettings = computed(() => app.settings?.queue || [])
const systemSettings = computed(() => app.settings?.system || [])
const complianceSettings = computed(() => app.settings?.compliance || [])

async function loadSettings() {
  loading.value = true
  try {
    await app.fetchSettings()
    const all = [
      ...(app.settings?.model || []),
      ...(app.settings?.queue || []),
      ...(app.settings?.system || []),
      ...(app.settings?.compliance || []),
    ]
    all.forEach((item) => {
      editableValues[item.key] = item.value
    })
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  userLoading.value = true
  try {
    users.value = (await userApi.list({ limit: 200 })).items
  } finally {
    userLoading.value = false
  }
}

async function saveSettings(keys) {
  const items = keys
    .filter((key) => editableValues[key] !== undefined)
    .map((key) => ({ key, value: editableValues[key] }))

  if (!items.length) {
    ElMessage.warning('没有可保存的修改')
    return
  }

  saving.value = true
  try {
    const result = await app.updateSettings(items)
    ElMessage.success(result.message)
  } finally {
    saving.value = false
  }
}

function openUserDialog() {
  Object.assign(userForm, {
    username: '',
    password: '',
    display_name: '',
    role: 'viewer',
    status: 'active',
  })
  userDialog.value = true
}

async function submitUser() {
  const valid = await userFormRef.value?.validate().catch(() => false)
  if (!valid) return

  userSubmitting.value = true
  try {
    await userApi.create(userForm)
    ElMessage.success('用户创建成功')
    userDialog.value = false
    await loadUsers()
  } finally {
    userSubmitting.value = false
  }
}

async function changeRole(user, role) {
  try {
    await ElMessageBox.confirm(
      `确认把「${user.display_name || user.username}」的角色改为 ${role} 吗？修改后立即生效。`,
      '修改角色',
      { type: 'warning' },
    )
  } catch {
    await loadUsers()
    return
  }
  await userApi.update(user.id, { role })
  ElMessage.success('角色已更新（该用户下次请求即生效）')
  await loadUsers()
}

async function toggleStatus(user) {
  const next = user.status === 'active' ? 'disabled' : 'active'
  await userApi.update(user.id, { status: next })
  ElMessage.success(next === 'active' ? '账号已启用' : '账号已停用')
  await loadUsers()
}

onMounted(async () => {
  await loadSettings()
  await loadUsers().catch(() => {})
})
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h1 class="page-title">系统设置</h1>
        <p class="page-subtitle">模型配置、用户角色、系统参数与任务队列配置</p>
      </div>
      <el-button :icon="'Refresh'" @click="loadSettings">刷新</el-button>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 模型配置 -->
      <el-tab-pane label="模型配置" name="model">
        <el-alert type="info" :closable="false" class="mb-12">
          <template #title>
            当前内容生成提供方：<b>{{ app.activeProviderLabel }}</b>（{{ app.runtime?.active_provider }}）。
            第一版内置确定性模拟生成，无需 API Key 即可离线演示；接入真实大模型时只需实现
            AiProvider 接口并在提供方注册表登记，业务代码无需改动。
          </template>
        </el-alert>

        <div class="section-title">提供方</div>
        <el-descriptions :column="2" border class="mb-16">
          <el-descriptions-item label="当前提供方">
            {{ app.runtime?.active_provider || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="可用提供方">
            <el-tag v-for="name in app.runtime?.available_providers || []" :key="name" size="small"
                    effect="plain" class="mr-6">{{ name }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <div class="section-title">模型参数</div>
        <el-table :data="modelSettings" border>
          <el-table-column prop="key" label="配置项" width="240">
            <template #default="{ row }"><span class="text-mono">{{ row.key }}</span></template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="220" />
          <el-table-column label="值" width="280">
            <template #default="{ row }">
              <el-input v-if="row.editable" v-model="editableValues[row.key]" size="small" />
              <span v-else class="text-muted">{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column label="可修改" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.editable ? 'success' : 'info'" size="small" effect="plain">
                {{ row.editable ? '是' : '只读' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div class="mt-12">
          <el-button type="primary" :loading="saving"
                     @click="saveSettings(modelSettings.filter((s) => s.editable).map((s) => s.key))">
            保存模型配置
          </el-button>
        </div>
      </el-tab-pane>

      <!-- 任务队列配置 -->
      <el-tab-pane label="任务队列配置" name="queue">
        <el-alert type="success" :closable="false" class="mb-12">
          <template #title>
            队列参数保存后立即生效，无需重启服务。当前工作进程：{{ app.workerStatus?.worker_id || '—' }}
            （{{ app.workerRunning ? '运行中' : '未运行' }}），
            执行中任务 {{ app.workerStatus?.inflight_jobs?.length || 0 }} 个，
            已完成轮询 {{ app.workerStatus?.loop_count || 0 }} 次。
          </template>
        </el-alert>

        <el-table :data="queueSettings" border>
          <el-table-column prop="key" label="配置项" width="260">
            <template #default="{ row }"><span class="text-mono">{{ row.key }}</span></template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="240" />
          <el-table-column label="值" width="200">
            <template #default="{ row }">
              <el-input v-model="editableValues[row.key]" size="small" :disabled="!row.editable" />
            </template>
          </el-table-column>
        </el-table>

        <div class="mt-12">
          <el-button type="primary" :loading="saving"
                     @click="saveSettings(queueSettings.filter((s) => s.editable).map((s) => s.key))">
            保存队列配置
          </el-button>
          <el-button :icon="'Refresh'" @click="app.fetchWorkerStatus()">刷新进程状态</el-button>
        </div>

        <div class="section-title mt-16">当前生效值</div>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="轮询间隔（秒）">
            {{ app.queueConfig.poll_interval_sec }}
          </el-descriptions-item>
          <el-descriptions-item label="任务超时（秒）">
            {{ app.queueConfig.job_timeout_sec }}
          </el-descriptions-item>
          <el-descriptions-item label="最大尝试次数">
            {{ app.queueConfig.max_attempts }}
          </el-descriptions-item>
          <el-descriptions-item label="并发数">{{ app.queueConfig.concurrency }}</el-descriptions-item>
          <el-descriptions-item label="模拟耗时（秒）">
            {{ app.queueConfig.simulate_seconds }}
          </el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <!-- 用户角色 -->
      <el-tab-pane label="用户角色" name="users">
        <el-alert type="warning" :closable="false" class="mb-12">
          <template #title>
            用户管理仅管理员可操作。角色修改后立即生效（每次请求都会重新读取用户角色）。
            管理员不能修改自己的角色或停用自己的账号，避免把自己锁在系统外。
          </template>
        </el-alert>

        <div class="toolbar mb-12">
          <el-button v-permission="['admin']" type="primary" :icon="'Plus'" @click="openUserDialog">
            创建用户
          </el-button>
          <el-button :icon="'Refresh'" @click="loadUsers">刷新</el-button>
        </div>

        <el-table v-loading="userLoading" :data="users" border>
          <el-table-column prop="username" label="用户名" width="140">
            <template #default="{ row }"><span class="text-mono">{{ row.username }}</span></template>
          </el-table-column>
          <el-table-column prop="display_name" label="展示名" width="150" />
          <el-table-column label="角色" width="170">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'operator' ? 'primary' : 'info'"
                      size="small">
                {{ row.role === 'admin' ? '管理员' : row.role === 'operator' ? '运营人员' : '查看人员' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }"><StatusTag :value="row.status" /></template>
          </el-table-column>
          <el-table-column label="最近登录" width="170">
            <template #default="{ row }">
              <span class="text-small">{{ formatDateTime(row.last_login_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <template v-if="app.runtime !== null">
                <el-dropdown v-permission="['admin']" class="mr-8"
                             @command="(role) => changeRole(row, role)">
                  <el-button size="small" text type="primary">
                    修改角色<el-icon><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="admin">管理员</el-dropdown-item>
                      <el-dropdown-item command="operator">运营人员</el-dropdown-item>
                      <el-dropdown-item command="viewer">查看人员</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button v-permission="['admin']" size="small" text
                           :type="row.status === 'active' ? 'danger' : 'success'"
                           @click="toggleStatus(row)">
                  {{ row.status === 'active' ? '停用' : '启用' }}
                </el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 系统参数 -->
      <el-tab-pane label="系统参数" name="system">
        <div class="section-title">业务参数</div>
        <el-table :data="systemSettings" border>
          <el-table-column prop="key" label="配置项" width="280">
            <template #default="{ row }"><span class="text-mono">{{ row.key }}</span></template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="240" />
          <el-table-column label="值" width="220">
            <template #default="{ row }">
              <el-input v-model="editableValues[row.key]" size="small" :disabled="!row.editable" />
            </template>
          </el-table-column>
        </el-table>
        <div class="mt-12">
          <el-button type="primary" :loading="saving"
                     @click="saveSettings(systemSettings.filter((s) => s.editable).map((s) => s.key))">
            保存系统参数
          </el-button>
        </div>

        <div class="section-title mt-16">合规声明（只读）</div>
        <el-table :data="complianceSettings" border>
          <el-table-column prop="key" label="配置项" width="320">
            <template #default="{ row }"><span class="text-mono">{{ row.key }}</span></template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="300" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="success" size="small" effect="plain">
                {{ row.value === '1' ? '已启用' : '未启用' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="userDialog" title="创建用户" width="480px">
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password
                    placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="展示名">
          <el-input v-model="userForm.display_name" placeholder="例如：张三" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option label="管理员（全部权限）" value="admin" />
            <el-option label="运营人员（业务编辑 + 投放确认）" value="operator" />
            <el-option label="查看人员（只读）" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialog = false">取消</el-button>
        <el-button type="primary" :loading="userSubmitting" @click="submitUser">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mr-6 {
  margin-right: 6px;
}

.mr-8 {
  margin-right: 8px;
}
</style>
