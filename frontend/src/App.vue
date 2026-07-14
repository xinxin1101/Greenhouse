<script setup lang="ts">
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  acknowledgeAllGreenhouseAlarms,
  acknowledgeGreenhouseAlarm,
  acknowledgeGreenhouseAlarms,
  fetchGreenhouseAlarms,
  fetchGreenhouseCurveTrace,
  fetchGreenhouseHistoryMeta,
  fetchGreenhouseState,
  fetchPointClouds,
  fetchSummary,
  fetchSystemStatus,
  fetchTrend,
  cancelGreenhouseCurve,
  exportGreenhouseHistory,
  queryGreenhouseHistory,
  startGreenhouseCurve,
  updateGreenhouseControl,
  updateGreenhouseFan,
  updateGreenhouseTargets
} from './api/client'
import GreenhouseOperationsPanel from './components/GreenhouseOperationsPanel.vue'
import GreenhouseCurvePanel from './components/GreenhouseCurvePanel.vue'
import GreenhouseHistoryPanel from './components/GreenhouseHistoryPanel.vue'
import GreenhouseAlarmLogPanel from './components/GreenhouseAlarmLogPanel.vue'
import MetricCards from './components/MetricCards.vue'
import PointCloudViewer from './components/PointCloudViewer.vue'
import SystemStatusPanel from './components/SystemStatusPanel.vue'
import TrendChart from './components/TrendChart.vue'
import type {
  DataSource,
  EnvironmentSummary,
  EnvironmentTrendPoint,
  GreenhouseAlarmEvent,
  GreenhouseCurveRequest,
  GreenhouseHistoryQuery,
  GreenhouseHistoryResult,
  GreenhouseRealtimeState,
  GreenhouseTargetsUpdate,
  GreenhouseView,
  MetricMode,
  PointCloudRecord,
  SystemStatus,
  TrendMode
} from './types/sensor'

const entered = ref(false)
const loading = ref(false)
const error = ref('')
const summary = ref<EnvironmentSummary>({ latest: null, totalCount: 0 })
const trend = ref<EnvironmentTrendPoint[]>([])
const clouds = ref<PointCloudRecord[]>([])
const dataSource = ref<DataSource>('sensor')
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
const greenhouseState = ref<GreenhouseRealtimeState | null>(null)
const greenhouseAlarms = ref<GreenhouseAlarmEvent[]>([])
const greenhouseLoading = ref(false)
const greenhouseActionLoading = ref(false)
const greenhouseError = ref('')
const greenhouseView = ref<GreenhouseView>('operations')
const greenhouseTrace = ref<unknown>(null)
const greenhouseTraceLoading = ref(false)
const greenhouseHistory = ref<GreenhouseHistoryResult | null>(null)
const greenhouseHistoryMeta = ref<Record<string, unknown> | null>(null)
const greenhouseHistoryLoading = ref(false)
let refreshTimer: number | null = null
let greenhouseRefreshTimer: number | null = null
let loadSequence = 0

const latest = computed(() => summary.value.latest)
const availableClouds = computed(() => clouds.value.filter((item) => item.fileExists))
const missingClouds = computed(() => clouds.value.filter((item) => !item.fileExists).length)
const currentCloud = computed(() => availableClouds.value[activeCloudIndex.value] ?? null)
const lastUpdated = computed(() => latest.value?.recordTime?.replace('T', ' ') ?? '--')
const dataSourceLabel = computed(() => dataSource.value === 'sensor' ? '传感器数据' : '温室环境数据')
const deviceLabel = computed(() => dataSource.value === 'sensor' ? '设备编号' : 'PLC 编号')
const statusTailLabel = computed(() => dataSource.value === 'sensor' ? '点云文件' : '当前报警')
const statusTailValue = computed(() => dataSource.value === 'sensor'
  ? `${availableClouds.value.length}${missingClouds.value ? ` / 缺失 ${missingClouds.value}` : ''}`
  : String(greenhouseState.value?.active_alarm_count ?? greenhouseAlarms.value.filter((alarm) => alarm.active).length)
)
const metricLabel = computed(() => {
  const labels: Record<MetricMode, string> = {
    all: '全部指标',
    temperature: '温度',
    humidity: '湿度',
    co2: 'CO₂',
    light: dataSource.value === 'sensor' ? '光照' : '灯组'
  }
  return labels[metric.value]
})
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
  const sequence = ++loadSequence
  const selectedSource = dataSource.value
  loading.value = true
  error.value = ''
  try {
    const params = {
      mode: mode.value,
      start: toApiDate(startDate.value),
      end: toApiDate(endDate.value, true),
      limit: 300
    }
    const [summaryData, trendData] = await Promise.all([
      fetchSummary(selectedSource),
      fetchTrend(selectedSource, params)
    ])
    const cloudData = selectedSource === 'sensor'
      ? await fetchPointClouds({ start: params.start, end: params.end })
      : []
    if (sequence !== loadSequence) return
    summary.value = summaryData
    trend.value = trendData
    clouds.value = cloudData
    if (activeCloudIndex.value >= availableClouds.value.length) {
      activeCloudIndex.value = 0
    }
    if (selectedSource === 'greenhouse') {
      void loadGreenhouseOperations()
    }
  } catch (err) {
    if (sequence !== loadSequence) return
    error.value = err instanceof Error ? err.message : '数据加载失败'
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function loadGreenhouseOperations() {
  greenhouseLoading.value = true
  greenhouseError.value = ''
  try {
    const [state, alarms] = await Promise.all([
      fetchGreenhouseState(),
      fetchGreenhouseAlarms(greenhouseView.value === 'alarms' ? 5000 : 100)
    ])
    greenhouseState.value = state
    greenhouseAlarms.value = alarms
    if (typeof state.targets.temperature === 'number') {
      targetTemperature.value = state.targets.temperature
    }
  } catch (err) {
    greenhouseError.value = err instanceof Error ? err.message : '温室 PLC 状态加载失败'
  } finally {
    greenhouseLoading.value = false
  }
}

async function runGreenhouseAction(action: () => Promise<unknown>) {
  greenhouseActionLoading.value = true
  greenhouseError.value = ''
  try {
    await action()
    await Promise.all([loadGreenhouseOperations(), loadDashboard()])
  } catch (err) {
    greenhouseError.value = greenhouseActionErrorMessage(err)
  } finally {
    greenhouseActionLoading.value = false
  }
}

function greenhouseActionErrorMessage(err: unknown) {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data
    if (body && typeof body === 'object') {
      const message = 'message' in body ? body.message : ('detail' in body ? body.detail : undefined)
      if (typeof message === 'string' && message.trim()) return message
    }
  }
  return err instanceof Error ? err.message : '温室 PLC 操作失败'
}

function setGreenhouseTargets(payload: GreenhouseTargetsUpdate) {
  void runGreenhouseAction(() => updateGreenhouseTargets(payload))
}

function setGreenhouseControl(device: 'system' | 'compressor' | 'uv' | 'co2', state: boolean) {
  void runGreenhouseAction(() => updateGreenhouseControl(device, state))
}

function setGreenhouseFan(state: boolean) {
  void runGreenhouseAction(() => updateGreenhouseFan(state))
}

function acknowledgeAlarms() {
  void runGreenhouseAction(acknowledgeGreenhouseAlarms)
}

function acknowledgeAllAlarms() {
  const plcIds = [...new Set(
    greenhouseAlarms.value
      .filter((alarm) => !alarm.acknowledged)
      .map((alarm) => alarm.plcId)
  )]
  void runGreenhouseAction(() => acknowledgeAllGreenhouseAlarms(plcIds))
}

function acknowledgeAlarmEvent(alarm: GreenhouseAlarmEvent) {
  void runGreenhouseAction(() => acknowledgeGreenhouseAlarm(alarm.id, alarm.plcId))
}

async function loadGreenhouseTrace(sensor: 'temperature' | 'humidity' | 'co2' = 'temperature') {
  greenhouseTraceLoading.value = true
  greenhouseError.value = ''
  try {
    greenhouseTrace.value = await fetchGreenhouseCurveTrace(sensor)
  } catch (err) {
    greenhouseError.value = err instanceof Error ? err.message : '温室曲线读取失败'
  } finally {
    greenhouseTraceLoading.value = false
  }
}

function startCurve(payload: GreenhouseCurveRequest) {
  void runGreenhouseAction(async () => {
    await startGreenhouseCurve(payload)
    await loadGreenhouseTrace(payload.sensor)
  })
}

function cancelCurve(sensor: 'temperature' | 'humidity' | 'co2') {
  void runGreenhouseAction(async () => {
    await cancelGreenhouseCurve(sensor)
    await loadGreenhouseTrace(sensor)
  })
}

async function loadGreenhouseHistoryMeta() {
  try {
    greenhouseHistoryMeta.value = await fetchGreenhouseHistoryMeta()
  } catch (err) {
    greenhouseError.value = err instanceof Error ? err.message : '温室历史信息读取失败'
  }
}

async function queryHistory(payload: GreenhouseHistoryQuery) {
  greenhouseHistoryLoading.value = true
  greenhouseError.value = ''
  try {
    greenhouseHistory.value = await queryGreenhouseHistory(payload)
  } catch (err) {
    greenhouseError.value = err instanceof Error ? err.message : '温室历史数据查询失败'
  } finally {
    greenhouseHistoryLoading.value = false
  }
}

async function exportHistory(payload: GreenhouseHistoryQuery) {
  greenhouseHistoryLoading.value = true
  greenhouseError.value = ''
  try {
    const response = await exportGreenhouseHistory(payload)
    const filename = response.headers['content-disposition']?.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename ? decodeURIComponent(filename) : 'greenhouse-history.csv'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (err) {
    greenhouseError.value = err instanceof Error ? err.message : '温室历史数据导出失败'
  } finally {
    greenhouseHistoryLoading.value = false
  }
}

function selectGreenhouseView(next: GreenhouseView) {
  greenhouseView.value = next
  if (next === 'curves') void loadGreenhouseTrace()
  if (next === 'history') void loadGreenhouseHistoryMeta()
  if (next === 'alarms') void loadGreenhouseOperations()
}

function selectDataSource(next: DataSource) {
  if (dataSource.value === next) return
  dataSource.value = next
  greenhouseView.value = 'operations'
  metric.value = 'all'
  summary.value = { latest: null, totalCount: 0 }
  trend.value = []
  void loadDashboard()
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

  greenhouseRefreshTimer = window.setInterval(() => {
    if (entered.value && dataSource.value === 'greenhouse') {
      void loadGreenhouseOperations()
    }
  }, 1000)
}

onMounted(() => {
  setupRefresh()
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (greenhouseRefreshTimer) window.clearInterval(greenhouseRefreshTimer)
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
        <span>{{ deviceLabel }}</span>
        <strong>{{ latest?.sourceId ?? '--' }}</strong>
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
        <span>{{ statusTailLabel }}</span>
        <strong>{{ statusTailValue }}</strong>
      </article>
    </section>

    <section class="toolbar" aria-label="筛选条件">
      <fieldset class="control-group data-source-control">
        <legend>数据来源</legend>
        <div class="source-selector">
          <label :class="{ active: dataSource === 'sensor' }">
            <input
              type="radio"
              name="environment-source"
              value="sensor"
              :checked="dataSource === 'sensor'"
              @change="selectDataSource('sensor')"
            />
            <span>
              <strong>传感器数据</strong>
              <small>节点采集</small>
            </span>
          </label>
          <label :class="{ active: dataSource === 'greenhouse' }">
            <input
              type="radio"
              name="environment-source"
              value="greenhouse"
              :checked="dataSource === 'greenhouse'"
              @change="selectDataSource('greenhouse')"
            />
            <span>
              <strong>温室环境</strong>
              <small>PLC 采集</small>
            </span>
          </label>
        </div>
      </fieldset>
      <div class="control-group wide">
        <span class="control-label">时间粒度</span>
        <div class="segmented">
          <button :class="{ active: mode === 'realtime' }" @click="selectMode('realtime')">实时数据</button>
          <button :class="{ active: mode === 'hour' }" @click="selectMode('hour')">每小时</button>
          <button :class="{ active: mode === 'day' }" @click="selectMode('day')">每天</button>
          <button :class="{ active: mode === 'week' }" @click="selectMode('week')">每周</button>
        </div>
      </div>
      <div v-if="dataSource === 'greenhouse'" class="control-group greenhouse-view-control">
        <span class="control-label">温室功能</span>
        <div class="segmented greenhouse-tabs">
          <button :class="{ active: greenhouseView === 'operations' }" @click="selectGreenhouseView('operations')">运行总览</button>
          <button :class="{ active: greenhouseView === 'curves' }" @click="selectGreenhouseView('curves')">曲线控制</button>
          <button :class="{ active: greenhouseView === 'history' }" @click="selectGreenhouseView('history')">历史数据</button>
          <button :class="{ active: greenhouseView === 'alarms' }" @click="selectGreenhouseView('alarms')">报警记录</button>
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
      <label v-if="dataSource === 'sensor'" class="control-group compact-input">
        <span>目标温度</span>
        <input v-model.number="targetTemperature" type="number" step="0.5" />
      </label>
      <button class="primary-small" @click="applyRange">应用筛选</button>
    </section>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section class="dashboard-grid" :class="{ loading, 'greenhouse-focus-grid': dataSource === 'greenhouse' && greenhouseView !== 'operations' }">
      <article v-if="dataSource === 'sensor'" class="panel point-cloud-panel">
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

      <GreenhouseOperationsPanel
        v-else-if="greenhouseView === 'operations'"
        :state="greenhouseState"
        :alarms="greenhouseAlarms"
        :loading="greenhouseLoading"
        :action-loading="greenhouseActionLoading"
        :error="greenhouseError"
        @refresh="loadGreenhouseOperations"
        @targets="setGreenhouseTargets"
        @control="setGreenhouseControl"
        @fan="setGreenhouseFan"
        @acknowledge="acknowledgeAlarms"
      />

      <GreenhouseCurvePanel
        v-else-if="greenhouseView === 'curves'"
        :state="greenhouseState"
        :trace="greenhouseTrace as any"
        :loading="greenhouseTraceLoading"
        :action-loading="greenhouseActionLoading"
        :error="greenhouseError"
        @start="startCurve"
        @cancel="cancelCurve"
        @trace="loadGreenhouseTrace"
      />

      <GreenhouseHistoryPanel
        v-else-if="greenhouseView === 'history'"
        :result="greenhouseHistory"
        :meta="greenhouseHistoryMeta"
        :loading="greenhouseHistoryLoading"
        :error="greenhouseError"
        @query="queryHistory"
        @export="exportHistory"
      />

      <GreenhouseAlarmLogPanel
        v-else
        :alarms="greenhouseAlarms"
        :loading="greenhouseLoading"
        :action-loading="greenhouseActionLoading"
        :error="greenhouseError"
        @refresh="loadGreenhouseOperations"
        @acknowledge="acknowledgeAlarms"
        @acknowledge-all="acknowledgeAllAlarms"
        @acknowledge-one="acknowledgeAlarmEvent"
      />

      <article v-if="dataSource === 'sensor' || greenhouseView === 'operations'" class="panel chart-panel">
        <div class="panel-heading">
          <div>
            <p>{{ dataSource === 'sensor' ? 'Sensor Trend' : 'Greenhouse Trend' }}</p>
            <h2>数据监测</h2>
          </div>
          <span class="mode-pill">{{ dataSourceLabel }} · {{ modeLabel }} · {{ metricLabel }}</span>
        </div>
        <TrendChart
          :points="trend"
          :point-clouds="availableClouds"
          :metric="metric"
          :target-temperature="targetTemperature"
          :source="dataSource"
        />
      </article>

      <MetricCards
        v-if="dataSource === 'sensor' || greenhouseView === 'operations'"
        :latest="latest"
        :selected="metric"
        :source="dataSource"
        :greenhouse-state="greenhouseState"
        @select="metric = $event"
      />
    </section>
  </main>
</template>
