<script setup>
import { computed } from 'vue'
import { splitLines } from '@/utils/format'

/**
 * AI 输出的结构化展示块：
 * 文本按换行拆成条目，数组则渲染为带序号的列表；两种形态都支持编辑态。
 */
const props = defineProps({
  label: { type: String, default: '' },
  /** 字符串（按行）或数组 */
  value: { type: [String, Array], default: '' },
  /** 数组项的标题字段（对象数组时使用） */
  titleKey: { type: String, default: '' },
  /** 数组项的内容字段（对象数组时使用） */
  contentKey: { type: String, default: '' },
  ordered: { type: Boolean, default: true },
})

const items = computed(() => {
  const value = props.value
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      if (item && typeof item === 'object') {
        const title = props.titleKey ? item[props.titleKey] : ''
        const content = props.contentKey ? item[props.contentKey] : ''
        return { key: index, title, content: content || JSON.stringify(item) }
      }
      return { key: index, title: '', content: String(item) }
    })
  }
  return splitLines(value).map((line, index) => ({ key: index, title: '', content: line }))
})

const isEmpty = computed(() => items.value.length === 0)
</script>

<template>
  <div class="ai-block">
    <div v-if="label" class="ai-block-label">{{ label }}</div>
    <el-empty v-if="isEmpty" description="暂无内容" :image-size="48" />
    <template v-else>
      <div v-for="(item, index) in items" :key="item.key" class="ai-item">
        <span v-if="ordered" class="ai-index">{{ index + 1 }}.</span>
        <div class="ai-content">
          <div v-if="item.title" class="ai-item-title">{{ item.title }}</div>
          <div class="pre-wrap">{{ item.content }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai-item {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-item:last-child {
  margin-bottom: 0;
}

.ai-index {
  flex: 0 0 auto;
  color: var(--el-color-primary);
  font-weight: 600;
  font-size: 13px;
  line-height: 1.75;
}

.ai-content {
  flex: 1 1 auto;
  font-size: 13.5px;
  line-height: 1.75;
  color: #303133;
}

.ai-item-title {
  font-weight: 600;
  margin-bottom: 2px;
}
</style>
