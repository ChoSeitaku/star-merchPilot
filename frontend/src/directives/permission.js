import { useAuthStore } from '@/stores/auth'

/**
 * v-permission 指令：角色不匹配时直接把元素从 DOM 中移除。
 *
 * 用法：
 *   <el-button v-permission="['admin']">用户管理</el-button>
 *   <el-button v-permission="['admin','operator']">生成诊断</el-button>
 *
 * 说明：这只是界面层的收敛，真正的权限校验始终在后端。
 */
export const permissionDirective = {
  mounted(el, binding) {
    const auth = useAuthStore()
    const allowed = binding.value
    if (!allowed || !Array.isArray(allowed) || allowed.length === 0) return
    if (!allowed.includes(auth.role)) {
      el.parentNode?.removeChild(el)
    }
  },
}

/** 在模板里判断角色（用于需要逻辑判断而非直接隐藏的场景）。 */
export function usePermission() {
  const auth = useAuthStore()
  const hasRole = (...roles) => roles.includes(auth.role)
  return { hasRole, canEdit: auth.canEdit, isAdmin: auth.isAdmin }
}
