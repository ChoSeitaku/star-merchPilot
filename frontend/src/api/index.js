/**
 * 接口层：每个领域一个导出对象，方法名对应业务动作。
 * 统一走 http 实例（已处理令牌注入、401 跳转与错误提示）。
 */
import http from './http'

// ------------------------------------------------------------------ 认证
export const authApi = {
  login: (payload) => http.post('/auth/login', payload),
  me: () => http.get('/auth/me'),
}

// ---------------------------------------------------------------- 用户管理
export const userApi = {
  list: (params) => http.get('/users', { params }),
  create: (payload) => http.post('/users', payload),
  update: (userId, payload) => http.patch(`/users/${userId}`, payload),
}

// ------------------------------------------------------------------ 店铺
export const storeApi = {
  list: (params) => http.get('/stores', { params }),
  create: (payload) => http.post('/stores', payload),
  detail: (storeId) => http.get(`/stores/${storeId}`),
  update: (storeId, payload) => http.patch(`/stores/${storeId}`, payload),
  accounts: (storeId) => http.get(`/stores/${storeId}/platform-accounts`),
  createAccount: (storeId, payload) => http.post(`/stores/${storeId}/platform-accounts`, payload),
  startAuthorization: (storeId, accountId, payload) =>
    http.post(`/stores/${storeId}/platform-accounts/${accountId}/authorization/start`, payload),
  authorizationCallback: (storeId, accountId, payload) =>
    http.post(
      `/stores/${storeId}/platform-accounts/${accountId}/authorization/callback-placeholder`,
      payload,
    ),
  inventoryAdvice: (storeId) => http.post(`/stores/${storeId}/inventory-advice/generate`),
  skuStock: (storeId) => http.get(`/stores/${storeId}/sku-stock`),
}

// ------------------------------------------------------------------ 商品
export const productApi = {
  list: (params) => http.get('/products', { params }),
  create: (payload) => http.post('/products', payload),
  detail: (productId) => http.get(`/products/${productId}`),
  update: (productId, payload) => http.patch(`/products/${productId}`, payload),
  remove: (productId) => http.delete(`/products/${productId}`),
  timeline: (productId) => http.get(`/products/${productId}/timeline`),

  mappings: (productId) => http.get(`/products/${productId}/platform-mappings`),
  createMapping: (productId, payload) => http.post(`/products/${productId}/platform-mappings`, payload),

  skus: (productId) => http.get(`/products/${productId}/skus`),
  createSku: (productId, payload) => http.post(`/products/${productId}/skus`, payload),
  updateSku: (productId, skuId, payload) => http.patch(`/products/${productId}/skus/${skuId}`, payload),
  skuMovements: (productId, skuId) => http.get(`/products/${productId}/skus/${skuId}/movements`),
  adjustInventory: (productId, skuId, payload) =>
    http.post(`/products/${productId}/skus/${skuId}/inventory/adjust`, payload),

  inventory: (productId) => http.get(`/products/${productId}/inventory`),
  movements: (productId) => http.get(`/products/${productId}/inventory/movements`),
}

// ------------------------------------------------------------------ 竞品
export const competitorApi = {
  list: (productId) => http.get(`/products/${productId}/competitors`),
  create: (productId, payload) => http.post(`/products/${productId}/competitors`, payload),
  update: (productId, competitorId, payload) =>
    http.patch(`/products/${productId}/competitors/${competitorId}`, payload),
  remove: (productId, competitorId) =>
    http.delete(`/products/${productId}/competitors/${competitorId}`),

  parseTasks: (productId) => http.get(`/products/${productId}/link-parse-tasks`),
  createParseTasks: (productId, payload) =>
    http.post(`/products/${productId}/competitors/import-url-tasks`, payload),
  runParseTask: (productId, taskId) =>
    http.post(`/products/${productId}/link-parse-tasks/${taskId}/run`),

  monitors: (productId) => http.get(`/products/${productId}/competitor-monitors`),
  createMonitor: (productId, competitorId, payload) =>
    http.post(`/products/${productId}/competitors/${competitorId}/monitor`, payload),
  updateMonitor: (productId, monitorId, params) =>
    http.patch(`/products/${productId}/competitor-monitors/${monitorId}`, null, { params }),
  snapshots: (productId, monitorId) =>
    http.get(`/products/${productId}/competitor-monitors/${monitorId}/snapshots`),
  runDue: (productId) => http.post(`/products/${productId}/competitor-monitors/run-due`),
}

// ------------------------------------------------------------------ 诊断
export const diagnosisApi = {
  list: (productId) => http.get(`/products/${productId}/diagnoses`),
  latest: (productId) => http.get(`/products/${productId}/diagnoses/latest`),
  generate: (productId, payload) => http.post(`/products/${productId}/diagnoses/generate`, payload),
  update: (productId, diagnosisId, payload) =>
    http.patch(`/products/${productId}/diagnoses/${diagnosisId}`, payload),
}

// -------------------------------------------------------------- 方案与素材
export const creativeApi = {
  list: (productId, params) => http.get(`/products/${productId}/creative-plans`, { params }),
  detail: (productId, planId) => http.get(`/products/${productId}/creative-plans/${planId}`),
  generateMainImages: (productId) =>
    http.post(`/products/${productId}/creative-plans/main-images/generate`),
  generateVideoScripts: (productId) =>
    http.post(`/products/${productId}/creative-plans/video-scripts/generate`),
  updatePlan: (productId, planId, payload) =>
    http.patch(`/products/${productId}/creative-plans/${planId}`, payload),
  removePlan: (productId, planId) => http.delete(`/products/${productId}/creative-plans/${planId}`),

  generateImages: (productId, planId, payload) =>
    http.post(`/products/${productId}/creative-plans/${planId}/images/generate`, payload),
  generateVideos: (productId, planId, payload) =>
    http.post(`/products/${productId}/creative-plans/${planId}/videos/generate`, payload),
  updateAssets: (productId, planId, payload) =>
    http.patch(`/products/${productId}/creative-plans/${planId}/assets`, payload),
}

// ------------------------------------------------------------------ 任务
export const jobApi = {
  list: (params) => http.get('/generation-jobs', { params }),
  productJobs: (productId, params) =>
    http.get(`/products/${productId}/generation-jobs`, { params }),
  detail: (productId, jobId) => http.get(`/products/${productId}/generation-jobs/${jobId}`),
  events: (productId, jobId) => http.get(`/products/${productId}/generation-jobs/${jobId}/events`),
  retry: (productId, jobId) => http.post(`/products/${productId}/generation-jobs/${jobId}/retry`),
  cancel: (productId, jobId) => http.post(`/products/${productId}/generation-jobs/${jobId}/cancel`),
  simulateFailure: (productId, jobId, payload) =>
    http.post(`/products/${productId}/generation-jobs/${jobId}/simulate-failure`, payload),
  sweepTimeouts: () => http.post('/workspace/generation-jobs/sweep-timeouts'),
}

// ------------------------------------------------------------------ 素材
export const assetApi = {
  list: (productId, params) => http.get(`/products/${productId}/assets`, { params }),
  sync: (productId) => http.post(`/products/${productId}/assets/sync`),
  updateReview: (productId, payload) => http.patch(`/products/${productId}/assets/review`, payload),
}

// ------------------------------------------------------------------ 链接
export const linkApi = {
  list: (productId) => http.get(`/products/${productId}/promotion-links`),
  generate: (productId) => http.post(`/products/${productId}/promotion-links/generate`),
  create: (productId, payload) => http.post(`/products/${productId}/promotion-links`, payload),
  update: (productId, linkId, payload) =>
    http.patch(`/products/${productId}/promotion-links/${linkId}`, payload),
  clicks: (productId, linkId) => http.get(`/products/${productId}/promotion-links/${linkId}/clicks`),
}

// ------------------------------------------------------------------ 投放
export const adApi = {
  recommendations: (productId) => http.get(`/products/${productId}/ad-recommendations`),
  generateRecommendation: (productId, payload) =>
    http.post(`/products/${productId}/ad-recommendations/generate`, payload),
  confirmRecommendation: (productId, recId, payload) =>
    http.patch(`/products/${productId}/ad-recommendations/${recId}/confirmation`, payload),

  experiments: (productId) => http.get(`/products/${productId}/ad-experiments`),
  generateExperiment: (productId, payload) =>
    http.post(`/products/${productId}/ad-experiments/generate`, payload),
  updateExperiment: (productId, expId, payload) =>
    http.patch(`/products/${productId}/ad-experiments/${expId}`, payload),
}

// --------------------------------------------------------- 经营数据与复盘
export const performanceApi = {
  list: (productId) => http.get(`/products/${productId}/performance-records`),
  create: (productId, payload) => http.post(`/products/${productId}/performance-records`, payload),
  importPreview: (productId, formData) =>
    http.post(`/products/${productId}/performance-records/import?preview_only=true`, formData),
  importConfirm: (productId, importId) =>
    http.post(
      `/products/${productId}/performance-records/import?preview_only=false&import_id=${importId}`,
    ),
}

export const reviewApi = {
  list: (productId) => http.get(`/products/${productId}/review-reports`),
  latest: (productId) => http.get(`/products/${productId}/review-reports/latest`),
  generate: (productId, payload) =>
    http.post(`/products/${productId}/review-reports/generate`, payload),
  update: (productId, reportId, payload) =>
    http.patch(`/products/${productId}/review-reports/${reportId}`, payload),
}

// ------------------------------------------------------------ 导入与工作区
export const importApi = {
  types: () => http.get('/imports'),
  preview: (importType, formData, params) =>
    http.post(`/imports/${importType}/preview`, formData, { params }),
  confirm: (importType, params) => http.post(`/imports/${importType}/confirm`, null, { params }),
  templateUrl: (importType) =>
    ({
      products: '/api/v1/workspace/templates/products',
      'sku-inventory': '/api/v1/workspace/templates/sku-inventory',
      'platform-mappings': '/api/v1/workspace/templates/platform-mappings',
    })[importType] || '',
}

export const workspaceApi = {
  dashboard: (params) => http.get('/workspace/dashboard', { params }),
  demoData: (force = false) => http.post('/workspace/demo-data', null, { params: { force } }),
  templates: () => http.get('/workspace/templates'),
  workerStatus: () => http.get('/workspace/worker-status'),
  runDueMonitors: () => http.post('/workspace/competitor-monitors/run-due'),
  settings: (params) => http.get('/workspace/settings', { params }),
  updateSettings: (payload) => http.patch('/workspace/settings', payload),
}

/** 下载 xlsx 模板（需要携带令牌，因此用 axios 取 blob 再触发下载）。 */
export async function downloadTemplate(importType) {
  const url = importApi.templateUrl(importType)
  const blob = await http.get(url.replace('/api/v1', ''), { responseType: 'blob' })
  const objectUrl = window.URL.createObjectURL(new Blob([blob]))
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = `${importType}-template.xlsx`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(objectUrl)
}
