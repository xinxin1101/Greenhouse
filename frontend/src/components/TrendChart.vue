<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import type { MetricMode, PointCloudRecord, SensorTrendPoint } from '../types/sensor'

const props = defineProps<{
  points: SensorTrendPoint[]
  pointClouds: PointCloudRecord[]
  metric: MetricMode
  targetTemperature: number
}>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const option = computed(() => {
  const x = props.points.map((p) => p.recordTime)
  const series: echarts.SeriesOption[] = []
  const markLines = props.pointClouds.map((p) => ({ xAxis: p.recordTime, name: '点云' }))

  if (props.metric === 'all' || props.metric === 'temperature') {
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
    series.push({
      type: 'line',
      name: '目标温度',
      data: props.points.map(() => props.targetTemperature),
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1.5, color: '#777', type: 'dotted' }
    })
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
      name: '光照',
      yAxisIndex: props.metric === 'all' ? 1 : 0,
      data: props.points.map((p) => p.lightIntensity),
      smooth: true,
      lineStyle: { width: 2, color: '#e6a23c', type: 'dashed' },
      itemStyle: { color: '#e6a23c' }
    })
  }

  return {
    color: ['#e25656', '#777', '#2a9d8f', '#e6a23c'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 8, itemWidth: 16, itemHeight: 8, textStyle: { color: '#506158' } },
    grid: { left: 42, right: props.metric === 'all' ? 48 : 18, top: 52, bottom: 30 },
    xAxis: { type: 'category', data: x, axisLabel: { hideOverlap: true, color: '#6c7a70' } },
    yAxis: props.metric === 'all'
      ? [
          { type: 'value', name: '温度/湿度', nameTextStyle: { color: '#6c7a70' }, axisLabel: { color: '#6c7a70' } },
          { type: 'value', name: '光照', position: 'right', nameTextStyle: { color: '#6c7a70' }, axisLabel: { color: '#6c7a70' } }
        ]
      : [{ type: 'value', axisLabel: { color: '#6c7a70' } }],
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

onMounted(() => {
  render()
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

watch(option, render, { deep: true })
</script>

<template>
  <div ref="chartEl" class="trend-chart"></div>
</template>
