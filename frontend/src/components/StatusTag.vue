<script setup>
import { computed } from 'vue'
import { statusLabel, statusType } from '@/utils/format'

const props = defineProps({
  value: { type: String, default: '' },
  label: { type: String, default: '' },
  size: { type: String, default: 'small' },
  effect: { type: String, default: 'light' },
})

const text = computed(() => props.label || statusLabel(props.value))
const type = computed(() => statusType(props.value))
</script>

<template>
  <el-tag :type="type" :size="size" :effect="effect">{{ text }}</el-tag>
</template>
