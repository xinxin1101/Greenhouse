<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import type { GreenhouseCurvePlan, GreenhouseCurveRequest, GreenhouseRealtimeState } from '../types/sensor'

type CurveTrace = {
  plan: GreenhouseCurvePlan | null
  actual: { rows?: Array<Record<string, number | string | null>> }
} | null

const props = defineProps<{
  state: GreenhouseRealtimeState | null
  trace: CurveTrace
  loading: boolean
  actionLoading: boolean
  error: string
}>()

const emit = defineEmits<{
  start: [payload: GreenhouseCurveRequest]
  cancel: [sensor: 'temperature' | 'humidity' | 'co2']
  trace: [sensor: 'temperature' | 'humidity' | 'co2']
}>()

const sensor = ref<'temperature' | 'humidity' | 'co2'>('temperature')
const startValue = ref(25)
const endValue = ref(27)
const duration = ref(600)
const interval = ref(10)
const shape = ref<GreenhouseCurveRequest['shape']>('linear')
const chartEl = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const labels = { temperature: '温度', humidity: '湿度', co2: 'CO2' }
const units = { temperature: '°C', humidity: '%RH', co2: 'ppm' }
const activeCurves = computed(() => Object.entries(props.state?.curves ?? {}) as Array<[string, GreenhouseCurvePlan]>)

function syncStartValue() {
  const target = props.state?.targets?.[sensor.value]
  if (typeof target === 'number') startValue.value = target
}

function submit() {
  emit('start', {
    sensor: sensor.value,
    start_value: startValue.value,
    end_value: endValue.value,
    duration_seconds: duration.value,
    interval_seconds: interval.value,
    shape: shape.value
  })
}

function plannedValue(plan: GreenhouseCurvePlan, timestamp: number) {
  const raw = Math.min(1, Math.max(0, (timestamp - plan.start_timestamp) / (plan.end_timestamp - plan.start_timestamp)))
  const progress = plan.shape === 'smooth' ? raw * raw * (3 - 2 * raw) : plan.shape === 'step' ? (raw < 0.5 ? 0 : 1) : raw
  return plan.start_value + (plan.end_value - plan.start_value) * progress
}

const chartOption = computed(() => {
  const trace = props.trace
  const plan = trace?.plan
  const points = trace?.actual?.rows ?? []
  const selected = sensor.value
  const timestamps = points.map((row) => Number(row.timestamp))
  const actual = points.map((row) => typeof row[selected] === 'number' ? row[selected] : null)
  const planned = plan ? timestamps.map((timestamp) => plannedValue(plan, timestamp)) : []
  return {
    color: ['#c75050', '#277b8d'],
    tooltip: { trigger: 'axis' },
    legend: { top: 4, textStyle: { color: '#506158' } },
    grid: { left: 46, right: 24, top: 38, bottom: 34 },
    xAxis: {
      type: 'category',
      data: timestamps.map((timestamp) => new Date(timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })),
      axisLabel: { color: '#6c7a70', hideOverlap: true }
    },
    yAxis: { type: 'value', name: units[selected], axisLabel: { color: '#6c7a70' } },
    series: [
      { type: 'line', name: '预设曲线', data: planned, smooth: false, symbol: 'none', lineStyle: { width: 2, type: 'dashed' } },
      { type: 'line', name: '实际曲线', data: actual, smooth: true, symbolSize: 5, lineStyle: { width: 2.5 } }
    ],
    graphic: plan ? undefined : { type: 'text', left: 'center', top: 'middle', style: { text: '尚未设置该参数的变化曲线', fill: '#819087', fontSize: 14 } }
  }
})

function renderChart() {
  if (!chart && chartEl.value) chart = echarts.init(chartEl.value)
  chart?.setOption(chartOption.value, true)
}

watch(sensor, () => {
  syncStartValue()
  emit('trace', sensor.value)
})
watch(() => props.state?.targets, syncStartValue, { immediate: true })
watch(chartOption, renderChart, { deep: true })

onMounted(() => {
  renderChart()
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartEl.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <article class="panel greenhouse-workspace-panel greenhouse-curve-panel">
    <div class="panel-heading">
      <div><p>Profile Control</p><h2>变化曲线控制</h2></div>
      <button class="icon-button" title="刷新实际曲线" :disabled="loading" @click="emit('trace', sensor)">↻</button>
    </div>
    <div class="workspace-content">
      <p v-if="error" class="greenhouse-error">{{ error }}</p>
      <section class="workspace-section curve-form-section">
        <div class="greenhouse-section-heading"><h3>新建控制曲线</h3><span>手动写入同一参数会自动终止对应曲线</span></div>
        <div class="curve-fields">
          <label><span>控制参数</span><select v-model="sensor"><option value="temperature">温度</option><option value="humidity">湿度</option><option value="co2">CO2</option></select></label>
          <label><span>起始值</span><input v-model.number="startValue" type="number" step="0.1" /></label>
          <label><span>结束值</span><input v-model.number="endValue" type="number" step="0.1" /></label>
          <label><span>持续时间（秒）</span><input v-model.number="duration" type="number" min="5" max="86400" /></label>
          <label><span>写入周期（秒）</span><input v-model.number="interval" type="number" min="1" max="3600" /></label>
          <label><span>变化方式</span><select v-model="shape"><option value="linear">线性</option><option value="smooth">平滑</option><option value="step">阶跃</option></select></label>
        </div>
        <button class="primary-small" :disabled="actionLoading" @click="submit">启动曲线</button>
      </section>
      <section class="workspace-section">
        <div class="greenhouse-section-heading"><h3>执行中的曲线</h3><span>{{ activeCurves.length }} 项</span></div>
        <div v-if="activeCurves.length" class="curve-active-list">
          <div v-for="[key, curve] in activeCurves" :key="key" class="curve-active-row">
            <div><strong>{{ labels[key as keyof typeof labels] }}</strong><small>{{ curve.start_value }} → {{ curve.end_value }} {{ units[key as keyof typeof units] }}</small></div>
            <div class="curve-progress"><span :style="{ width: `${Math.round(curve.progress * 100)}%` }"></span></div>
            <small>剩余 {{ Math.ceil(curve.remaining_seconds) }} 秒</small>
            <button class="secondary-action compact" :disabled="actionLoading" @click="emit('cancel', key as 'temperature' | 'humidity' | 'co2')">取消</button>
          </div>
        </div>
        <p v-else class="panel-empty">当前没有执行中的变化曲线</p>
      </section>
      <section class="workspace-section curve-trace-section">
        <div class="greenhouse-section-heading"><h3>预设与实际对比</h3><span>{{ labels[sensor] }} · {{ trace?.plan?.status ?? '未开始' }}</span></div>
        <div ref="chartEl" class="curve-trace-chart"></div>
      </section>
    </div>
  </article>
</template>
