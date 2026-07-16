<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { GreenhouseAlarmEvent } from '../types/sensor'

const props = defineProps<{ alarms: GreenhouseAlarmEvent[]; loading: boolean; actionLoading: boolean; error: string }>()
const emit = defineEmits<{ refresh: []; acknowledge: []; acknowledgeAll: []; acknowledgeOne: [alarm: GreenhouseAlarmEvent] }>()

const activeAlarmCount = computed(() => props.alarms.filter((alarm) => alarm.active).length)
const unacknowledgedAlarmCount = computed(() => props.alarms.filter((alarm) => !alarm.acknowledged).length)
const currentAckTitle = computed(() => activeAlarmCount.value ? '确认当前仍在激活的报警' : '当前没有激活中的报警')
const allAckTitle = computed(() => unacknowledgedAlarmCount.value ? '确认所有未确认报警记录' : '当前没有待确认的报警记录')
const refreshPending = ref(false)
const refreshObservedLoading = ref(false)
const refreshFeedback = ref('')
let refreshFeedbackTimer: number | null = null

watch(
  () => props.loading,
  (loading) => {
    if (!refreshPending.value) return
    if (loading) {
      refreshObservedLoading.value = true
      return
    }
    if (refreshObservedLoading.value) {
      refreshPending.value = false
      refreshObservedLoading.value = false
      refreshFeedback.value = props.error ? '刷新失败' : '已刷新'
      if (refreshFeedbackTimer) window.clearTimeout(refreshFeedbackTimer)
      refreshFeedbackTimer = window.setTimeout(() => {
        refreshFeedback.value = ''
      }, 1800)
    }
  }
)

function refreshNow() {
  if (props.loading) return
  refreshPending.value = true
  refreshObservedLoading.value = false
  refreshFeedback.value = '刷新中'
  emit('refresh')
}

onBeforeUnmount(() => {
  if (refreshFeedbackTimer) window.clearTimeout(refreshFeedbackTimer)
})
</script>

<template>
  <article class="panel greenhouse-workspace-panel greenhouse-alarm-panel">
    <div class="panel-heading">
      <div><p>Alarm Archive</p><h2>报警事件记录</h2></div>
      <div class="refresh-control">
        <span v-if="refreshFeedback" class="refresh-feedback" :class="{ pending: refreshPending, error }">{{ refreshFeedback }}</span>
        <button class="icon-button refresh-button" :class="{ refreshing: refreshPending }" title="刷新报警记录" :disabled="loading" @click="refreshNow">↻</button>
      </div>
    </div>
    <div class="workspace-content">
      <p v-if="error" class="greenhouse-error">{{ error }}</p>
      <section class="workspace-section">
        <div class="greenhouse-section-heading alarm-log-heading">
          <div><h3>全部报警</h3><span>{{ activeAlarmCount }} 项当前激活 · {{ unacknowledgedAlarmCount }} 项待确认</span></div>
          <div class="alarm-log-actions">
            <button class="secondary-action compact" :title="currentAckTitle" :disabled="!activeAlarmCount || actionLoading" @click="emit('acknowledge')">确认当前报警</button>
            <button class="secondary-action compact" :title="allAckTitle" :disabled="!unacknowledgedAlarmCount || actionLoading" @click="emit('acknowledgeAll')">确认全部未确认</button>
          </div>
        </div>
        <div class="data-table-wrap alarm-table-wrap"><table class="data-table"><thead><tr><th>状态</th><th>PLC</th><th>报警名称</th><th>说明</th><th>开始时间</th><th>恢复时间</th><th>确认状态</th><th>操作</th></tr></thead><tbody><tr v-for="alarm in alarms" :key="alarm.id"><td><span class="alarm-status" :class="{ active: alarm.active }">{{ alarm.active ? '激活' : '已恢复' }}</span></td><td>{{ alarm.plcId }}</td><td>{{ alarm.alarmName }}</td><td>{{ alarm.message }}</td><td>{{ alarm.startedAt.replace('T', ' ') }}</td><td>{{ alarm.clearedAt?.replace('T', ' ') ?? '--' }}</td><td><span class="alarm-acknowledgement" :class="{ pending: !alarm.acknowledged }">{{ alarm.acknowledged ? '已确认' : '未确认' }}</span></td><td><button v-if="!alarm.acknowledged" class="secondary-action compact alarm-ack-action" :disabled="actionLoading" @click="emit('acknowledgeOne', alarm)">确认</button><span v-else class="alarm-action-complete">--</span></td></tr><tr v-if="!alarms.length"><td colspan="8" class="empty-cell">暂无报警事件</td></tr></tbody></table></div>
      </section>
    </div>
  </article>
</template>
