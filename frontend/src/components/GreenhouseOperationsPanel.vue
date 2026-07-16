<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type {
  GreenhouseAlarmEvent,
  GreenhouseRealtimeState,
  GreenhouseTargetsUpdate
} from '../types/sensor'

const props = defineProps<{
  state: GreenhouseRealtimeState | null
  alarms: GreenhouseAlarmEvent[]
  loading: boolean
  actionLoading: boolean
  error: string
}>()

const emit = defineEmits<{
  refresh: []
  targets: [payload: GreenhouseTargetsUpdate]
  control: [device: 'system' | 'compressor' | 'uv' | 'co2', state: boolean]
  fan: [state: boolean]
  acknowledge: []
}>()

const temperature = ref<number | null>(null)
const humidity = ref<number | null>(null)
const co2 = ref<number | null>(null)
const temperatureDirty = ref(false)
const humidityDirty = ref(false)
const co2Dirty = ref(false)
const manualRefreshPending = ref(false)
const refreshObservedLoading = ref(false)
const refreshFeedback = ref('')
const targetValidationMessage = ref('')
let refreshFeedbackTimer: number | null = null

const targetLimits = {
  temperature: { label: '温度', min: -20, max: 60, unit: '℃' },
  humidity: { label: '湿度', min: 0, max: 100, unit: '%RH' },
  co2: { label: 'CO₂', min: 0, max: 10000, unit: 'ppm' }
} as const

watch(
  () => props.state?.targets,
  (targets) => {
    if (!targets) return
    syncTarget(temperature, temperatureDirty, targets.temperature)
    syncTarget(humidity, humidityDirty, targets.humidity)
    syncTarget(co2, co2Dirty, targets.co2)
  },
  { immediate: true }
)

watch(
  () => props.loading,
  (loading) => {
    if (!manualRefreshPending.value) return
    if (loading) {
      refreshObservedLoading.value = true
      return
    }
    if (refreshObservedLoading.value) {
      manualRefreshPending.value = false
      refreshObservedLoading.value = false
      refreshFeedback.value = props.error ? '刷新失败' : '已刷新'
      if (refreshFeedbackTimer) window.clearTimeout(refreshFeedbackTimer)
      refreshFeedbackTimer = window.setTimeout(() => {
        refreshFeedback.value = ''
      }, 1800)
    }
  }
)

const connectionText = computed(() => props.state?.connected ? 'PLC 已连接' : 'PLC 未连接')
const activeAlarms = computed(() => props.alarms.filter((alarm) => alarm.active))
const visibleAlarms = computed(() => props.alarms.slice(0, 5))
const deviceRows = computed(() => {
  const controls = props.state?.controls ?? {}
  const labels = props.state?.control_labels ?? {}
  const running = props.state?.run_status ?? {}
  const interlocks = props.state?.interlocks ?? {}
  return [
    { key: 'system', label: labels.system ?? '系统总控', state: Boolean(controls.system), running: Boolean(controls.system), type: 'control' as const },
    { key: 'compressor', label: labels.compressor ?? '压机', state: Boolean(controls.compressor), running: Boolean(running.compressor), type: 'control' as const },
    { key: 'uv', label: labels.uv ?? '紫外', state: Boolean(controls.uv), running: Boolean(running.uv), type: 'control' as const },
    { key: 'co2', label: labels.co2 ?? 'CO₂', state: Boolean(controls.co2), running: Boolean(running.co2), type: 'control' as const },
    { key: 'fresh_air', label: labels.fresh_air ?? '新风', state: Boolean(controls.fresh_air), running: Boolean(running.fresh_air), type: 'fan' as const },
    { key: 'lamp', label: labels.lamp ?? '灯组', state: Boolean(controls.lamp), running: Boolean(running.lamp_group), type: 'light' as const }
  ].map((device) => ({
    ...device,
    blocked: !device.state && Boolean(interlocks[device.key]?.blocked),
    blockReason: interlocks[device.key]?.reason ?? null
  }))
})
const runRows = computed(() => {
  const states = props.state?.run_status ?? {}
  const labels = props.state?.run_status_labels ?? {}
  const fallbackLabels: Record<string, string> = {
    electric_heating: '电加热',
    compressor: '压缩机',
    circulation_fan: '循环风机',
    humidification: '加湿',
    dehumidification: '除湿',
    fresh_air: '新风',
    lighting: '照明',
    uv: '紫外',
    lamp_group: '灯组',
    co2: 'CO2'
  }
  return Object.keys(fallbackLabels).map((key) => ({
    key,
    label: labels[key] ?? fallbackLabels[key],
    running: Boolean(states[key])
  }))
})

function numberOrNull(value: number | null | undefined) {
  return typeof value === 'number' ? value : null
}

function syncTarget(
  draft: typeof temperature,
  dirty: typeof temperatureDirty,
  incoming: number | null | undefined
) {
  const next = numberOrNull(incoming)
  if (!dirty.value) {
    draft.value = next
    return
  }
  if (next !== null && draft.value !== null && Math.abs(next - draft.value) < 0.0001) {
    dirty.value = false
  }
}

function valueText(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' ? value.toFixed(digits) : '--'
}

function validateTargetValue(key: keyof typeof targetLimits, value: number | null) {
  if (value === null) return ''
  const limit = targetLimits[key]
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return `${limit.label}请输入有效数字。`
  }
  if (value < limit.min || value > limit.max) {
    return `${limit.label}设定范围为 ${limit.min} 到 ${limit.max} ${limit.unit}，请调整后再写入。`
  }
  return ''
}

function clearTargetValidation() {
  const validation =
    validateTargetValue('temperature', temperature.value) ||
    validateTargetValue('humidity', humidity.value) ||
    validateTargetValue('co2', co2.value)
  if (!validation) targetValidationMessage.value = ''
}

function applyTargets() {
  const validation =
    validateTargetValue('temperature', temperature.value) ||
    validateTargetValue('humidity', humidity.value) ||
    validateTargetValue('co2', co2.value)
  if (validation) {
    targetValidationMessage.value = validation
    return
  }
  const payload: GreenhouseTargetsUpdate = {}
  if (temperature.value !== null) payload.temperature = temperature.value
  if (humidity.value !== null) payload.humidity = humidity.value
  if (co2.value !== null) payload.co2 = co2.value
  if (Object.keys(payload).length) {
    targetValidationMessage.value = ''
    emit('targets', payload)
  }
}

function refreshNow() {
  if (props.loading || props.actionLoading) return
  manualRefreshPending.value = true
  refreshObservedLoading.value = false
  refreshFeedback.value = '刷新中'
  emit('refresh')
}

function changeDevice(
  row: { key: string; type: 'control' | 'fan' | 'light' },
  state: boolean
) {
  if (row.type === 'fan') {
    emit('fan', state)
  } else if (row.type === 'light') {
    emit('targets', { light: state })
  } else {
    emit('control', row.key as 'system' | 'compressor' | 'uv' | 'co2', state)
  }
}

onBeforeUnmount(() => {
  if (refreshFeedbackTimer) window.clearTimeout(refreshFeedbackTimer)
})
</script>

<template>
  <article class="panel greenhouse-panel" :class="{ loading }">
    <div class="panel-heading greenhouse-heading">
      <div>
        <p>Greenhouse Operations</p>
        <h2>温室运行</h2>
      </div>
      <div class="greenhouse-connection" :class="{ online: state?.connected }">
        <span></span>
        {{ connectionText }}
      </div>
    </div>

    <div class="greenhouse-content">
      <p v-if="error" class="greenhouse-error">{{ error }}</p>

      <section class="greenhouse-section target-section">
        <div class="greenhouse-section-heading">
          <h3>环境设定</h3>
          <button class="secondary-action compact" :disabled="actionLoading" @click="applyTargets">写入设定</button>
        </div>
        <div class="target-fields">
          <label>
            <span>温度 ℃</span>
            <input v-model.number="temperature" type="number" min="-20" max="60" step="0.1" :disabled="actionLoading" @input="temperatureDirty = true; clearTargetValidation()" />
          </label>
          <label>
            <span>湿度 %RH</span>
            <input v-model.number="humidity" type="number" min="0" max="100" step="0.1" :disabled="actionLoading" @input="humidityDirty = true; clearTargetValidation()" />
          </label>
          <label>
            <span>CO₂ ppm</span>
            <input v-model.number="co2" type="number" min="0" max="10000" step="1" :disabled="actionLoading" @input="co2Dirty = true; clearTargetValidation()" />
          </label>
        </div>
        <p v-if="targetValidationMessage" class="target-validation" role="alert">{{ targetValidationMessage }}</p>
        <div class="target-feedback">
          <span>PLC 设定反馈</span>
          <b>温度 {{ valueText(state?.feedback?.temperature) }} ℃</b>
          <b>湿度 {{ valueText(state?.feedback?.humidity) }} %RH</b>
          <b>CO2 {{ valueText(state?.feedback?.co2, 0) }} ppm</b>
        </div>
      </section>

      <section class="greenhouse-section">
        <div class="greenhouse-section-heading">
          <h3>设备控制</h3>
          <div class="refresh-control">
            <span v-if="refreshFeedback" class="refresh-feedback" :class="{ pending: manualRefreshPending }">{{ refreshFeedback }}</span>
            <button class="icon-button refresh-button" :class="{ refreshing: manualRefreshPending }" :title="manualRefreshPending ? '正在刷新 PLC 状态' : '立即刷新 PLC 状态'" :disabled="loading || actionLoading" @click="refreshNow">↻</button>
          </div>
        </div>
        <div class="device-list">
          <label v-for="device in deviceRows" :key="device.key" class="device-row" :class="{ blocked: device.blocked }" :title="device.blockReason ?? ''">
            <span>{{ device.label }}</span>
            <span class="device-state" :class="{ on: device.running, locked: device.blocked }">{{ device.blocked ? '互锁' : device.running ? '运行' : '待机' }}</span>
            <input
              class="toggle-input"
              type="checkbox"
              :checked="device.state"
              :disabled="!state?.connected || actionLoading || device.blocked"
              @change="changeDevice(device, ($event.target as HTMLInputElement).checked)"
            />
          </label>
        </div>
      </section>

      <section class="greenhouse-section run-status-section">
        <div class="greenhouse-section-heading">
          <h3>设备运行反馈</h3>
          <span>PLC 实际输出状态</span>
        </div>
        <div class="run-status-grid">
          <div v-for="item in runRows" :key="item.key" class="run-status-item" :class="{ on: item.running }">
            <span>{{ item.label }}</span>
            <b>{{ item.running ? '运行' : '待机' }}</b>
          </div>
        </div>
      </section>

      <section class="greenhouse-section alarm-section">
        <div class="greenhouse-section-heading">
          <div>
            <h3>报警事件</h3>
            <span>{{ activeAlarms.length }} 项当前激活</span>
          </div>
          <button class="secondary-action compact" :disabled="!activeAlarms.length || actionLoading" @click="emit('acknowledge')">确认报警</button>
        </div>
        <div v-if="visibleAlarms.length" class="alarm-list">
          <div v-for="alarm in visibleAlarms" :key="alarm.id" class="alarm-row" :class="{ active: alarm.active }">
            <span class="alarm-mark"></span>
            <div>
              <strong>{{ alarm.alarmName }}</strong>
              <small>{{ alarm.message }}</small>
            </div>
            <time>{{ alarm.startedAt.replace('T', ' ') }}</time>
          </div>
        </div>
        <p v-else class="panel-empty">暂无报警事件</p>
      </section>

      <section class="greenhouse-section measurement-section">
        <div class="measurement-item">
          <span>实际温度</span>
          <strong>{{ valueText(state?.measurements?.temperature) }} ℃</strong>
        </div>
        <div class="measurement-item">
          <span>实际湿度</span>
          <strong>{{ valueText(state?.measurements?.humidity) }} %</strong>
        </div>
        <div class="measurement-item">
          <span>实际 CO₂</span>
          <strong>{{ valueText(state?.measurements?.co2, 0) }} ppm</strong>
        </div>
      </section>
    </div>
  </article>
</template>
