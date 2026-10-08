<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { statusLabel } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const collapsed = ref(false)

/** 侧边菜单：只有 meta.menu 的路由才展示，并按角色过滤 */
const menuItems = computed(() => {
  const layout = router.getRoutes().find((r) => r.path === '/')
  const children = (layout?.children || []).filter((child) => child.meta?.menu)
  return children
    .filter((child) => {
      const roles = child.meta?.roles
      return !roles || !roles.length || roles.includes(auth.role)
    })
    .map((child) => ({
      path: child.path.startsWith('/') ? child.path : `/${child.path}`,
      title: child.meta.title,
      icon: child.meta.icon || 'Menu',
    }))
})

const activeMenu = computed(() => route.meta.activeMenu || route.path)

onMounted(async () => {
  // 顶栏需要展示「内容生成提供方」与「任务进程状态」，一次请求即可拿到两者。
  // 这里直接 await 并让错误冒泡到拦截器，避免接口名写错时被静默吞掉。
  if (!app.runtime) {
    await app.fetchSettings().catch(() => {})
  }
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '210px'" class="layout-aside">
      <div class="brand">
        <el-icon :size="22"><Shop /></el-icon>
        <span v-show="!collapsed" class="brand-text">电商运营助手</span>
      </div>

      <el-menu :default-active="activeMenu" :collapse="collapsed" router class="layout-menu">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-button text :icon="collapsed ? 'Expand' : 'Fold'" @click="collapsed = !collapsed" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">工作台</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title && route.name !== 'dashboard'">
              {{ route.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-tag
            :type="app.workerRunning ? 'success' : 'info'"
            size="small"
            effect="plain"
            class="worker-tag"
          >
            任务进程：{{ app.workerRunning ? '运行中' : '未运行' }}
          </el-tag>
          <el-tag size="small" effect="plain">模型：{{ app.activeProviderLabel }}</el-tag>

          <el-dropdown @command="handleLogout">
            <span class="user-chip">
              <el-icon><UserFilled /></el-icon>
              <span class="user-name">{{ auth.displayName }}</span>
              <el-tag size="small" :type="auth.isAdmin ? 'danger' : auth.canEdit ? 'primary' : 'info'">
                {{ statusLabel(auth.role) }}
              </el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <keep-alive :max="4">
            <component :is="Component" :key="route.fullPath" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.layout-aside {
  background: #1f2d3d;
  transition: width 0.22s;
  overflow-x: hidden;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 58px;
  padding: 0 18px;
  color: #fff;
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-text {
  letter-spacing: 0.5px;
}

.layout-menu {
  border-right: none;
  background: transparent;
}

.layout-menu :deep(.el-menu-item) {
  color: #c0c4cc;
}

.layout-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.layout-menu :deep(.el-menu-item.is-active) {
  background: var(--el-color-primary);
  color: #fff;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid var(--mp-border);
  height: 58px;
  padding: 0 18px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.worker-tag {
  margin-right: 2px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
}

.layout-main {
  padding: 0;
  background: var(--mp-bg);
  overflow-y: auto;
}
</style>
