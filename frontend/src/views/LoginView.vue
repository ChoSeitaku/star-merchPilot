<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

/** 演示账号：一键填充，方便课程演示 */
const demoAccounts = [
  { username: 'admin', password: 'admin123', label: '管理员', desc: '全部权限' },
  { username: 'operator', password: 'operator123', label: '运营人员', desc: '业务编辑 + 投放确认' },
  { username: 'viewer', password: 'viewer123', label: '查看人员', desc: '只读' },
]

function fill(account) {
  form.username = account.username
  form.password = account.password
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const data = await auth.login({ ...form })
    ElMessage.success(`欢迎回来，${data.user.display_name || data.user.username}`)
    router.push(route.query.redirect || '/dashboard')
  } catch {
    // 错误提示已在拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="login-intro">
        <h1 class="intro-title">电商运营助手</h1>
        <p class="intro-sub">面向中小电商团队的单品运营闭环工作台</p>

        <ul class="intro-list">
          <li>建店建档 → 录入商品 → 补充竞品 → 生成诊断</li>
          <li>主图方案 → 视频脚本 → 素材生成与人工审核</li>
          <li>投放建议 → 人工确认 → 经营数据回填 → 复盘报告</li>
          <li>复盘结论回到诊断环节，形成下一轮优化闭环</li>
        </ul>

        <div class="intro-note">
          合规提示：不保存明文密码 / 令牌 / Cookie；不实现绕过登录、验证码或风控的抓取；
          投放只产出建议与实验计划，不自动创建广告计划、不自动扣费。
        </div>
      </div>

      <div class="login-form-wrap">
        <h2 class="form-title">登录</h2>
        <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="submit">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" :prefix-icon="'User'" clearable />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              :prefix-icon="'Lock'"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" class="submit-btn" :loading="loading" @click="submit">
              登录
            </el-button>
          </el-form-item>
        </el-form>

        <el-divider>演示账号（点击填充）</el-divider>
        <div class="demo-accounts">
          <div
            v-for="account in demoAccounts"
            :key="account.username"
            class="demo-account"
            @click="fill(account)"
          >
            <div class="demo-account-label">{{ account.label }}</div>
            <div class="demo-account-name text-mono">{{ account.username }} / {{ account.password }}</div>
            <div class="demo-account-desc text-small text-muted">{{ account.desc }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #1f2d3d 0%, #2b5876 55%, #4e8ab8 100%);
}

.login-panel {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  width: min(980px, 100%);
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
}

.login-intro {
  padding: 44px 40px;
  background: #1f2d3d;
  color: #e6eaf0;
}

.intro-title {
  margin: 0;
  font-size: 27px;
  letter-spacing: 1px;
}

.intro-sub {
  margin: 10px 0 26px;
  font-size: 13.5px;
  color: #9fb0c3;
}

.intro-list {
  margin: 0 0 26px;
  padding-left: 18px;
  font-size: 13.5px;
  line-height: 2.05;
  color: #c8d4e0;
}

.intro-note {
  font-size: 12px;
  line-height: 1.85;
  color: #8b9bad;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 16px;
}

.login-form-wrap {
  padding: 44px 40px;
}

.form-title {
  margin: 0 0 22px;
  font-size: 21px;
}

.submit-btn {
  width: 100%;
}

.demo-accounts {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.demo-account {
  border: 1px dashed var(--mp-border);
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.18s;
}

.demo-account:hover {
  border-color: var(--el-color-primary);
  background: #f0f7ff;
}

.demo-account-label {
  font-size: 13px;
  font-weight: 600;
}

.demo-account-name {
  margin: 2px 0;
  color: #606266;
}

.demo-account-desc {
  line-height: 1.5;
}

@media (max-width: 860px) {
  .login-panel {
    grid-template-columns: 1fr;
  }

  .login-intro {
    display: none;
  }
}
</style>
