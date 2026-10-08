/** 状态 → 中文标签 / Element Plus 标签类型 的统一映射。 */

export const PLATFORM_LABELS = {
  taobao: '淘宝',
  tmall: '天猫',
  jd: '京东',
  pdd: '拼多多',
  douyin: '抖音',
  xiaohongshu: '小红书',
  other: '其他',
}

export const PLATFORM_OPTIONS = Object.entries(PLATFORM_LABELS).map(([value, label]) => ({
  value,
  label,
}))

const TAG_TYPES = ['primary', 'success', 'warning', 'danger', 'info']

const MAP = {
  // 商品状态
  draft: { label: '草稿', type: 'info' },
  active: { label: '在售', type: 'success' },
  inactive: { label: '停用', type: 'info' },
  // 方案状态
  selected: { label: '已选中', type: 'success' },
  archived: { label: '已归档', type: 'info' },
  // 任务状态
  pending: { label: '待执行', type: 'info' },
  running: { label: '执行中', type: 'primary' },
  succeeded: { label: '已成功', type: 'success' },
  failed: { label: '已失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
  timeout: { label: '已超时', type: 'warning' },
  // 投放确认
  confirmed: { label: '已确认', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  // 实验状态
  finished: { label: '已结束', type: 'success' },
  // 素材审核
  approved: { label: '已通过', type: 'success' },
  // 用户状态
  disabled: { label: '已停用', type: 'danger' },
  // 解析任务 / 监控
  paused: { label: '已暂停', type: 'info' },
  // 平台授权
  unauthorized: { label: '未授权', type: 'info' },
  pending_authorization: { label: '授权中', type: 'warning' },
  authorized: { label: '已授权', type: 'success' },
  // 用户角色
  admin: { label: '管理员', type: 'danger' },
  operator: { label: '运营人员', type: 'primary' },
  viewer: { label: '查看人员', type: 'info' },
}

export function statusLabel(value) {
  return MAP[value]?.label || value || '—'
}

export function statusType(value) {
  return MAP[value]?.type || 'info'
}

export function platformLabel(value) {
  return PLATFORM_LABELS[value] || value || '—'
}

/** 任务事件类型 → 时间线节点类型 */
export function eventTimelineType(eventType) {
  return (
    {
      enqueued: 'info',
      running: 'primary',
      succeeded: 'success',
      failed: 'danger',
      retry: 'warning',
      cancelled: 'info',
      timeout: 'warning',
    }[eventType] || 'info'
  )
}

export function eventLabel(eventType) {
  return (
    {
      enqueued: '入队',
      running: '运行中',
      succeeded: '成功',
      failed: '失败',
      retry: '重试',
      cancelled: '取消',
      timeout: '超时',
    }[eventType] || eventType
  )
}

export function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

export function formatDate(value) {
  if (!value) return '—'
  return String(value).slice(0, 10)
}

export function formatMoney(value, withSymbol = true) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (Number.isNaN(number)) return String(value)
  const text = number.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return withSymbol ? `¥${text}` : text
}

export function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  return Number.isNaN(number) ? String(value) : number.toLocaleString('zh-CN')
}

export function formatPercent(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  return Number.isNaN(number) ? String(value) : `${number.toFixed(digits)}%`
}

/** 把多行中文文本渲染成数组，便于用列表展示（AI 输出常带 1）2）编号）。 */
export function splitLines(text) {
  if (!text) return []
  return String(text)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

export { TAG_TYPES }
