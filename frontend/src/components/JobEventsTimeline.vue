<script setup>
import { eventLabel, eventTimelineType, formatDateTime } from '@/utils/format'

defineProps({
  /** 事件数组（来自 /generation-jobs/{id}/events） */
  events: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})
</script>

<template>
  <div v-loading="loading" class="timeline-wrap">
    <el-empty v-if="!events.length && !loading" description="暂无任务事件" :image-size="70" />
    <el-timeline v-else>
      <el-timeline-item
        v-for="event in events"
        :key="event.id"
        :type="eventTimelineType(event.event_type)"
        :timestamp="formatDateTime(event.created_at)"
        placement="top"
      >
        <div class="event-head">
          <el-tag :type="eventTimelineType(event.event_type)" size="small" effect="dark">
            {{ eventLabel(event.event_type) }}
          </el-tag>
        </div>
        <div class="event-message pre-wrap">{{ event.event_message }}</div>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<style scoped>
.timeline-wrap {
  min-height: 90px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 6px;
}

.event-head {
  margin-bottom: 4px;
}

.event-message {
  font-size: 13px;
  color: #606266;
}
</style>
