<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import type { ServiceStatus, SystemStatus } from '../types/sensor'

const props = defineProps<{
  status: SystemStatus | null
  loading: boolean
  error: string
}>()

const emit = defineEmits<{
  refresh: []
  close: []
}>()

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
      refreshFeedback.value = props.error ? '检查失败' : '已检查'
      if (refreshFeedbackTimer) window.clearTimeout(refreshFeedbackTimer)
      refreshFeedbackTimer = window.setTimeout(() => {
        refreshFeedback.value = ''
      }, 1800)
    }
  }
)

function services(status: SystemStatus | null): ServiceStatus[] {
  if (!status) return []
  return [status.api, status.database, status.collector, status.pointCloudDirectory]
}

function refreshNow() {
  if (props.loading) return
  refreshPending.value = true
  refreshObservedLoading.value = false
  refreshFeedback.value = '检查中'
  emit('refresh')
}

onBeforeUnmount(() => {
  if (refreshFeedbackTimer) window.clearTimeout(refreshFeedbackTimer)
})
</script>

<template>
  <section class="system-status-panel" aria-label="系统状态">
    <header>
      <div>
        <p>Runtime Check</p>
        <h2>系统状态</h2>
      </div>
      <div class="system-status-actions">
        <span v-if="refreshFeedback" class="refresh-feedback" :class="{ pending: refreshPending, error }">{{ refreshFeedback }}</span>
        <button class="secondary-action compact" :class="{ refreshing: refreshPending }" :disabled="loading" @click="refreshNow">
          {{ loading ? '检查中' : '重新检查' }}
        </button>
        <button class="ghost-action compact" @click="emit('close')">关闭</button>
      </div>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <div v-if="status" class="system-summary" :class="{ healthy: status.healthy, warning: !status.healthy }">
      <strong>{{ status.healthy ? '全部关键服务正常' : '存在未启动或异常的服务' }}</strong>
      <span>检查时间：{{ status.checkedAt.replace('T', ' ').slice(0, 19) }}</span>
    </div>

    <div class="system-service-grid">
      <article v-for="item in services(status)" :key="item.name" class="system-service-card" :class="{ online: item.running, offline: !item.running }">
        <span class="service-dot" />
        <div>
          <strong>{{ item.name }}</strong>
          <p>{{ item.detail }}</p>
        </div>
        <b>{{ item.running ? '正常' : '异常' }}</b>
      </article>
    </div>

    <p v-if="!status && !loading && !error" class="system-empty">点击“重新检查”查看后端和采集模块状态。</p>
  </section>
</template>
