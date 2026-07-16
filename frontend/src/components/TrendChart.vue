<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import type { DataSource, EnvironmentTrendPoint, MetricMode, PointCloudRecord } from '../types/sensor'

const props = defineProps<{
  points: EnvironmentTrendPoint[]
  pointClouds: PointCloudRecord[]
  metric: MetricMode
  targetTemperature: number | null
  source: DataSource
}>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const option = computed(() => {
  const x = props.points.map((p) => p.recordTime)
  const series: echarts.SeriesOption[] = []
  const markLines = props.pointClouds.map((p) => ({ xAxis: p.recordTime, name: '点云' }))
  const greenhouse = props.source === 'greenhouse'

  if (props.metric === 'all' || props.metric === 'temperature') {
    const targetTemperatureData = props.points.map((p) => (
      typeof p.targetTemperature === 'number' ? p.targetTemperature : props.targetTemperature
    ))
    series.push({
      type: 'line',
      name: '温度',
      data: props.points.map((p) => p.temperature),
      smooth: true,
      symbolSize: 5,
      lineStyle: { width: 2, color: '#e25656' },
      itemStyle: { color: '#e25656' },
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#2d7d46', type: 'dashed' }, data: markLines }
    })
    if (targetTemperatureData.some((value) => typeof value === 'number')) {
      series.push({
        type: 'line',
        name: '目标温度',
        data: targetTemperatureData,
        smooth: false,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#777', type: 'dotted' }
      })
    }
  }
  if (props.metric === 'all' || props.metric === 'humidity') {
    series.push({
      type: 'line',
      name: '湿度',
      data: props.points.map((p) => p.humidity),
      smooth: true,
      areaStyle: { color: 'rgba(42, 157, 143, 0.12)' },
      lineStyle: { width: 2, color: '#2a9d8f' },
      itemStyle: { color: '#2a9d8f' }
    })
  }
  if (props.metric === 'all' || props.metric === 'light') {
    series.push({
      type: 'line',
      name: greenhouse ? '灯组状态' : '光照',
      yAxisIndex: props.metric === 'all' ? (greenhouse ? 2 : 1) : 0,
      data: props.points.map((p) => greenhouse ? p.lightOn : p.lightIntensity),
      smooth: !greenhouse,
      step: greenhouse ? 'end' : false,
      lineStyle: { width: 2, color: '#e6a23c', type: 'dashed' },
      itemStyle: { color: '#e6a23c' }
    })
  }

  if (greenhouse && (props.metric === 'all' || props.metric === 'co2')) {
    series.push({
      type: 'line',
      name: 'CO₂',
      yAxisIndex: props.metric === 'all' ? 1 : 0,
      data: props.points.map((p) => p.co2),
      smooth: true,
      lineStyle: { width: 2, color: '#3978b8' },
      itemStyle: { color: '#3978b8' }
    })
  }

  const combinedAxes: echarts.YAXisComponentOption[] = greenhouse
    ? [
        { type: 'value', name: '温度/湿度', nameTextStyle: { color: '#6c7a70' }, axisLabel: { color: '#6c7a70' } },
        { type: 'value', name: 'CO₂', position: 'right', nameTextStyle: { color: '#3978b8' }, axisLabel: { color: '#3978b8' } },
        {
          type: 'value',
          name: '灯组',
          position: 'right',
          offset: 48,
          min: 0,
          max: 1,
          interval: 1,
          nameTextStyle: { color: '#9c6811' },
          axisLabel: { color: '#9c6811', formatter: (value: number) => value === 1 ? '开' : '关' }
        }
      ]
    : [
        { type: 'value', name: '温度/湿度', nameTextStyle: { color: '#6c7a70' }, axisLabel: { color: '#6c7a70' } },
        { type: 'value', name: '光照', position: 'right', nameTextStyle: { color: '#6c7a70' }, axisLabel: { color: '#6c7a70' } }
      ]

  const singleAxis: echarts.YAXisComponentOption = greenhouse && props.metric === 'light'
    ? {
        type: 'value',
        min: 0,
        max: 1,
        interval: 1,
        axisLabel: { color: '#6c7a70', formatter: (value: number) => value === 1 ? '开启' : '关闭' }
      }
    : { type: 'value', axisLabel: { color: '#6c7a70' } }

  return {
    color: ['#e25656', '#777', '#2a9d8f', '#e6a23c', '#3978b8'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 8, itemWidth: 16, itemHeight: 8, textStyle: { color: '#506158' } },
    grid: { left: 42, right: props.metric === 'all' ? (greenhouse ? 96 : 48) : 18, top: 52, bottom: 30 },
    xAxis: { type: 'category', data: x, axisLabel: { hideOverlap: true, color: '#6c7a70' } },
    yAxis: props.metric === 'all' ? combinedAxes : [singleAxis],
    graphic: props.points.length
      ? undefined
      : {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: greenhouse ? '暂无温室环境数据' : '暂无传感器数据',
            fill: '#819087',
            fontSize: 14
          }
        },
    series
  }
})

function render() {
  if (!chart && chartEl.value) {
    chart = echarts.init(chartEl.value)
  }
  chart?.setOption(option.value, true)
}

function resize() {
  chart?.resize()
}

function resizeAfterLayout() {
  requestAnimationFrame(() => {
    requestAnimationFrame(resize)
  })
}

onMounted(() => {
  render()
  resizeAfterLayout()
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(chartEl.value)
  }
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
  resizeObserver = null
})

watch(option, async () => {
  await nextTick()
  render()
  resizeAfterLayout()
}, { deep: true })
</script>

<template>
  <div ref="chartEl" class="trend-chart"></div>
</template>
