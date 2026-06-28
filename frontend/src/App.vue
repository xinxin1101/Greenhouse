<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { fetchPointClouds, fetchSummary, fetchSystemStatus, fetchTrend } from './api/client'
import MetricCards from './components/MetricCards.vue'
import PointCloudViewer from './components/PointCloudViewer.vue'
import SystemStatusPanel from './components/SystemStatusPanel.vue'
import TrendChart from './components/TrendChart.vue'
import type { MetricMode, PointCloudRecord, SensorSummary, SensorTrendPoint, SystemStatus, TrendMode } from './types/sensor'

const entered = ref(false)
const loading = ref(false)
const error = ref('')
const summary = ref<SensorSummary>({ latest: null, totalCount: 0 })
const trend = ref<SensorTrendPoint[]>([])
const clouds = ref<PointCloudRecord[]>([])
const mode = ref<TrendMode>('realtime')
const metric = ref<MetricMode>('all')
const targetTemperature = ref(25)
const activeCloudIndex = ref(0)
const playing = ref(true)
const startDate = ref('')
const endDate = ref('')
const statusOpen = ref(false)
const statusLoading = ref(false)
const statusError = ref('')
const systemStatus = ref<SystemStatus | null>(null)
let refreshTimer: number | null = null

const latest = computed(() => summary.value.latest)
const availableClouds = computed(() => clouds.value.filter((item) => item.fileExists))
const missingClouds = computed(() => clouds.value.filter((item) => !item.fileExists).length)
const currentCloud = computed(() => availableClouds.value[activeCloudIndex.value] ?? null)
const lastUpdated = computed(() => latest.value?.recordTime?.replace('T', ' ') ?? '--')
const modeLabel = computed(() => {
  const labels: Record<TrendMode, string> = {
    realtime: '实时数据',
    hour: '每小时',
    day: '每天',
    week: '每周'
  }
  return labels[mode.value]
})

function toApiDate(date: string, end = false) {
  if (!date) return undefined
  return `${date}T${end ? '23:59:59' : '00:00:00'}`
}

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      mode: mode.value,
      start: toApiDate(startDate.value),
      end: toApiDate(endDate.value, true),
      limit: 300
    }
    const [summaryData, trendData, cloudData] = await Promise.all([
      fetchSummary(),
      fetchTrend(params),
      fetchPointClouds({ start: params.start, end: params.end })
    ])
    summary.value = summaryData
    trend.value = trendData
    clouds.value = cloudData
    if (activeCloudIndex.value >= availableClouds.value.length) {
      activeCloudIndex.value = 0
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据加载失败'
  } finally {
    loading.value = false
  }
}

function selectMode(next: TrendMode) {
  mode.value = next
  void loadDashboard()
}

function applyRange() {
  void loadDashboard()
}

async function loadSystemStatus() {
  statusLoading.value = true
  statusError.value = ''
  try {
    systemStatus.value = await fetchSystemStatus()
  } catch (err) {
    statusError.value = err instanceof Error ? err.message : '系统状态检查失败'
  } finally {
    statusLoading.value = false
  }
}

function openSystemStatus() {
  statusOpen.value = true
  void loadSystemStatus()
}

function setupRefresh() {
  refreshTimer = window.setInterval(() => {
    if (entered.value && mode.value === 'realtime') {
      void loadDashboard()
    }
  }, 60000)
}

onMounted(() => {
  setupRefresh()
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <main v-if="!entered" class="welcome-view">
    <section class="welcome-panel" aria-label="系统入口">
      <div class="welcome-mark">SP</div>
      <p class="kicker">Sensor Platform</p>
      <h1>作物生长环境与表型关联分析系统</h1>
      <p class="welcome-subtitle">环境数据、趋势分析与点云表型联动展示</p>
      <button class="primary-action" @click="entered = true; loadDashboard()">进入系统</button>
    </section>
  </main>

  <main v-else class="dashboard-shell">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Crop Environment & Phenotype Monitor</p>
        <h1>作物生长环境与表型关联分析系统</h1>
      </div>
      <div class="header-actions">
        <button class="secondary-action" @click="openSystemStatus">系统状态</button>
        <button class="secondary-action" @click="loadDashboard">刷新数据</button>
        <button class="ghost-action" @click="entered = false">返回首页</button>
      </div>
    </header>

    <SystemStatusPanel
      v-if="statusOpen"
      :status="systemStatus"
      :loading="statusLoading"
      :error="statusError"
      @refresh="loadSystemStatus"
      @close="statusOpen = false"
    />

    <section class="status-strip">
      <article>
        <span>设备编号</span>
        <strong>{{ latest?.deviceId ?? '--' }}</strong>
      </article>
      <article>
        <span>最近更新</span>
        <strong>{{ lastUpdated }}</strong>
      </article>
      <article>
        <span>数据记录</span>
        <strong>{{ summary.totalCount }}</strong>
      </article>
      <article>
        <span>点云文件</span>
        <strong>{{ availableClouds.length }}<small v-if="missingClouds"> / 缺失 {{ missingClouds }}</small></strong>
      </article>
    </section>

    <section class="toolbar" aria-label="筛选条件">
      <div class="control-group wide">
        <span class="control-label">时间粒度</span>
        <div class="segmented">
          <button :class="{ active: mode === 'realtime' }" @click="selectMode('realtime')">实时数据</button>
          <button :class="{ active: mode === 'hour' }" @click="selectMode('hour')">每小时</button>
          <button :class="{ active: mode === 'day' }" @click="selectMode('day')">每天</button>
          <button :class="{ active: mode === 'week' }" @click="selectMode('week')">每周</button>
        </div>
      </div>
      <label class="control-group">
        <span>开始日期</span>
        <input v-model="startDate" type="date" />
      </label>
      <label class="control-group">
        <span>结束日期</span>
        <input v-model="endDate" type="date" />
      </label>
      <label class="control-group compact-input">
        <span>目标温度</span>
        <input v-model.number="targetTemperature" type="number" step="0.5" />
      </label>
      <button class="primary-small" @click="applyRange">应用筛选</button>
    </section>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section class="dashboard-grid" :class="{ loading }">
      <article class="panel point-cloud-panel">
        <div class="panel-heading">
          <div>
            <p>3D Phenotype</p>
            <h2>作物点云图</h2>
          </div>
          <div class="inline-controls">
            <button class="icon-button" @click="activeCloudIndex = Math.max(0, activeCloudIndex - 1)">‹</button>
            <span>{{ availableClouds.length ? activeCloudIndex + 1 : 0 }} / {{ availableClouds.length }}</span>
            <button class="icon-button" @click="activeCloudIndex = availableClouds.length ? (activeCloudIndex + 1) % availableClouds.length : 0">›</button>
            <button class="secondary-action compact" @click="playing = !playing">{{ playing ? '暂停轮播' : '开始轮播' }}</button>
          </div>
        </div>
        <PointCloudViewer
          :records="availableClouds"
          :active-index="activeCloudIndex"
          :playing="playing"
          @update-index="activeCloudIndex = $event"
        />
        <footer class="panel-foot">
          <span>{{ currentCloud?.fileName ?? '无点云文件' }}</span>
          <span>{{ currentCloud?.recordTime?.replace('T', ' ') ?? '--' }}</span>
        </footer>
      </article>

      <article class="panel chart-panel">
        <div class="panel-heading">
          <div>
            <p>Sensor Trend</p>
            <h2>数据监测</h2>
          </div>
          <span class="mode-pill">{{ modeLabel }} · {{ metric.toUpperCase() }}</span>
        </div>
        <TrendChart
          :points="trend"
          :point-clouds="availableClouds"
          :metric="metric"
          :target-temperature="targetTemperature"
        />
      </article>

      <MetricCards :latest="latest" :selected="metric" @select="metric = $event" />
    </section>
  </main>
</template>
