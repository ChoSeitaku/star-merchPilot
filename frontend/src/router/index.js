import { createRouter, createWebHashHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

/**
 * 路由表。
 * meta.roles 为空表示所有登录用户可访问；否则只有列出的角色可进入。
 * meta.title 用于侧边菜单与面包屑。
 */
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '首页工作台', icon: 'HomeFilled', menu: true },
      },
      {
        path: 'stores',
        name: 'stores',
        component: () => import('@/views/StoreListView.vue'),
        meta: { title: '店铺列表', icon: 'Shop', menu: true },
      },
      {
        path: 'stores/:id',
        name: 'store-detail',
        component: () => import('@/views/StoreDetailView.vue'),
        meta: { title: '店铺详情', activeMenu: '/stores' },
      },
      {
        path: 'products',
        name: 'products',
        component: () => import('@/views/ProductListView.vue'),
        meta: { title: '商品池', icon: 'Goods', menu: true },
      },
      {
        path: 'products/:id',
        name: 'product-detail',
        component: () => import('@/views/ProductDetailView.vue'),
        meta: { title: '商品详情', activeMenu: '/products' },
      },
      {
        path: 'imports',
        name: 'imports',
        component: () => import('@/views/ImportCenterView.vue'),
        meta: { title: '导入中心', icon: 'Upload', menu: true },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting', menu: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在', public: true },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    // 已登录用户不必再看登录页
    if (to.name === 'login' && auth.isLoggedIn) return { path: '/dashboard' }
    return true
  }

  if (!auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 首次进入或刷新后补齐用户信息（角色可能已被管理员调整）
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { name: 'login' }
    }
  }

  const roles = to.meta.roles
  if (roles && roles.length && !roles.includes(auth.role)) {
    ElMessage.error(`当前角色（${auth.displayName}）无权访问「${to.meta.title || to.path}」`)
    return { path: '/dashboard' }
  }

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 电商运营助手` : '电商运营助手'
})

export default router
