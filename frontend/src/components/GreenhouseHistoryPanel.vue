<script setup lang="ts">
import { computed, ref } from 'vue'
import TrendChart from './TrendChart.vue'
import type { EnvironmentTrendPoint, GreenhouseHistoryQuery, GreenhouseHistoryResult, GreenhouseHistorySensor } from '../types/sensor'

const props = defineProps<{ result: GreenhouseHistoryResult | null; meta: Record<string, unknown> | null; loading: boolean; error: string }>()
const emit = defineEmits<{ query: [payload: GreenhouseHistoryQuery]; export: [payload: GreenhouseHistoryQuery] }>()

const end = new Date()
const start = new Date(end.getTime() - 60 * 60 * 1000)
const toInput = (value: Date) => new Date(value.getTime() - value.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
const startTime = ref(toInput(start))
const endTime = ref(toInput(end))
const interval = ref(10)
const sensors = ref<GreenhouseHistorySensor[]>(['temperature', 'humidity', 'co2', 'light'])
const page = ref(1)
const pageSize = 6

const payload = computed<GreenhouseHistoryQuery>(() => ({
  start_timestamp: new Date(startTime.value).getTime() / 1000,
  end_timestamp: new Date(endTime.value).getTime() / 1000,
  interval_seconds: interval.value,
  sensors: sensors.value,
  limit: 5000
}))
const points = computed<EnvironmentTrendPoint[]>(() => (props.result?.rows ?? []).map((row) => ({ recordTime: row.time_text, temperature: row.temperature ?? null, humidity: row.humidity ?? null, co2: row.co2 ?? null, lightOn: row.light ?? null })))
const totalPages = computed(() => Math.max(1, Math.ceil((props.result?.rows.length ?? 0) / pageSize)))
const pageRows = computed(() => (props.result?.rows ?? []).slice((page.value - 1) * pageSize, page.value * pageSize))

function setRange(hours: number) {
  const nextEnd = new Date()
  startTime.value = toInput(new Date(nextEnd.getTime() - hours * 3600 * 1000))
  endTime.value = toInput(nextEnd)
}
function runQuery() { page.value = 1; emit('query', payload.value) }
function toggleSensor(name: GreenhouseHistorySensor) {
  sensors.value = sensors.value.includes(name) ? sensors.value.filter((sensor) => sensor !== name) : [...sensors.value, name]
}
function display(value: number | null | undefined, digits = 1) { return typeof value === 'number' ? value.toFixed(digits) : '--' }
</script>

<template>
  <article class="panel greenhouse-workspace-panel greenhouse-history-panel">
    <div class="panel-heading"><div><p>History Archive</p><h2>历史数据查看与下载</h2></div><span class="mode-pill">{{ meta?.raw_count ?? 0 }} 条归档记录</span></div>
    <div class="workspace-content">
      <p v-if="error" class="greenhouse-error">{{ error }}</p>
      <section class="workspace-section history-controls">
        <div class="quick-ranges"><button class="secondary-action compact" @click="setRange(1)">最近 1 小时</button><button class="secondary-action compact" @click="setRange(6)">最近 6 小时</button><button class="secondary-action compact" @click="setRange(24)">最近 1 天</button><button class="secondary-action compact" @click="setRange(168)">最近 7 天</button></div>
        <div class="history-fields">
          <label><span>开始时间</span><input v-model="startTime" type="datetime-local" /></label>
          <label><span>结束时间</span><input v-model="endTime" type="datetime-local" /></label>
          <label><span>采样周期（秒）</span><input v-model.number="interval" type="number" min="1" max="86400" /></label>
          <fieldset><legend>数据项</legend><label v-for="item in ['temperature', 'humidity', 'co2', 'light'] as GreenhouseHistorySensor[]" :key="item"><input type="checkbox" :checked="sensors.includes(item)" @change="toggleSensor(item)" />{{ { temperature: '温度', humidity: '湿度', co2: 'CO2', light: '灯组' }[item] }}</label></fieldset>
        </div>
        <div class="history-actions"><button class="primary-small" :disabled="loading || !sensors.length" @click="runQuery">查询并绘图</button><button class="secondary-action" :disabled="loading || !sensors.length" @click="emit('export', { ...payload, limit: 200000 })">导出 CSV</button></div>
      </section>
      <div class="history-results-grid">
        <section class="workspace-section history-chart-section">
          <div class="greenhouse-section-heading"><h3>选定时间段趋势</h3><span v-if="result">返回 {{ result.returned_count }} 条，原始 {{ result.raw_count }} 条</span></div>
          <TrendChart :points="points" :point-clouds="[]" metric="all" :target-temperature="0" source="greenhouse" />
        </section>
        <section class="workspace-section history-table-section">
          <div class="greenhouse-section-heading"><h3>检测数值</h3><span>每页 {{ pageSize }} 条 · 第 {{ result?.rows.length ? page : 0 }} / {{ result?.rows.length ? totalPages : 0 }} 页</span></div>
          <div class="data-table-wrap"><table class="data-table"><thead><tr><th>检测时间</th><th v-if="sensors.includes('temperature')">温度</th><th v-if="sensors.includes('humidity')">湿度</th><th v-if="sensors.includes('co2')">CO2</th><th v-if="sensors.includes('light')">灯组</th></tr></thead><tbody><tr v-for="row in pageRows" :key="row.timestamp"><td>{{ row.time_text.replace('T', ' ') }}</td><td v-if="sensors.includes('temperature')">{{ display(row.temperature) }}</td><td v-if="sensors.includes('humidity')">{{ display(row.humidity) }}</td><td v-if="sensors.includes('co2')">{{ display(row.co2, 0) }}</td><td v-if="sensors.includes('light')">{{ row.light ? '开启' : '关闭' }}</td></tr><tr v-if="!pageRows.length"><td :colspan="sensors.length + 1" class="empty-cell">所选时间段暂无数据</td></tr></tbody></table></div>
          <div class="table-pagination"><button class="icon-button" title="上一页" :disabled="page <= 1" @click="page--">←</button><button class="icon-button" title="下一页" :disabled="page >= totalPages" @click="page++">→</button></div>
        </section>
      </div>
    </div>
  </article>
</template>
