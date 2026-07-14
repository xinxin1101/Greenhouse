<script setup lang="ts">
import { computed } from 'vue'
import type { DataSource, EnvironmentReading, GreenhouseRealtimeState, MetricMode } from '../types/sensor'

const props = defineProps<{
  latest: EnvironmentReading | null
  selected: MetricMode
  source: DataSource
  greenhouseState?: GreenhouseRealtimeState | null
}>()

const emit = defineEmits<{
  select: [metric: MetricMode]
}>()

function fmt(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' ? value.toFixed(digits) : '--'
}

type MetricCard = {
  key: MetricMode
  icon: string
  title: string
  unit: string
  tone: string
  read: (latest: EnvironmentReading | null) => string
}

const cards = computed<MetricCard[]>(() => {
  const common: MetricCard[] = [
    {
      key: 'all',
      icon: '▦',
      title: '综合视图',
      unit: '全部指标',
      tone: 'slate',
      read: () => 'Overview'
    },
    {
      key: 'temperature',
      icon: '℃',
      title: '温度',
      unit: '摄氏度',
      tone: 'rose',
      read: (latest) => `${fmt(latest?.temperature)} ℃`
    },
    {
      key: 'humidity',
      icon: '%',
      title: '湿度',
      unit: '空气湿度',
      tone: 'teal',
      read: (latest) => `${fmt(latest?.humidity)} %`
    }
  ]

  if (props.source === 'greenhouse') {
    return [
      {
        key: 'all',
        icon: '▦',
        title: '综合视图',
        unit: '全部指标',
        tone: 'slate',
        read: () => 'Overview'
      },
      {
        key: 'temperature',
        icon: '℃',
        title: '温度',
        unit: '摄氏度',
        tone: 'rose',
        read: () => `${fmt(props.greenhouseState?.measurements?.temperature)} ℃`
      },
      {
        key: 'humidity',
        icon: '%',
        title: '湿度',
        unit: '空气湿度',
        tone: 'teal',
        read: () => `${fmt(props.greenhouseState?.measurements?.humidity)} %`
      },
      {
        key: 'co2',
        icon: 'CO₂',
        title: 'CO₂',
        unit: '浓度 · ppm',
        tone: 'blue',
        read: () => `${fmt(props.greenhouseState?.measurements?.co2, 0)} ppm`
      },
      {
        key: 'light',
        icon: '●',
        title: '灯组',
        unit: 'PLC 实际状态',
        tone: 'amber',
        read: () => props.greenhouseState?.run_status?.lamp_group == null
          ? '--'
          : props.greenhouseState.run_status.lamp_group ? '已开启' : '已关闭'
      }
    ]
  }

  return [
    ...common,
    {
      key: 'light',
      icon: 'lx',
      title: '光照',
      unit: 'Lux',
      tone: 'amber',
      read: (latest) => `${fmt(latest?.lightIntensity, 0)} Lux`
    }
  ]
})
</script>

<template>
  <aside class="metric-rail">
    <button
      v-for="card in cards"
      :key="card.key"
      class="metric-card"
      :class="[`tone-${card.tone}`, { active: selected === card.key }]"
      @click="emit('select', card.key)"
    >
      <span class="metric-accent" aria-hidden="true"></span>
      <span class="metric-icon">{{ card.icon }}</span>
      <span class="metric-copy">
        <strong>{{ card.title }}</strong>
        <small>{{ card.unit }}</small>
      </span>
      <span class="metric-value">{{ card.read(latest) }}</span>
    </button>
  </aside>
</template>
