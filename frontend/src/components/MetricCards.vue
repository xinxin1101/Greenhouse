<script setup lang="ts">
import type { MetricMode, SensorReading } from '../types/sensor'

defineProps<{
  latest: SensorReading | null
  selected: MetricMode
}>()

const emit = defineEmits<{
  select: [metric: MetricMode]
}>()

function fmt(value: number | undefined, digits = 1) {
  return typeof value === 'number' ? value.toFixed(digits) : '--'
}

const cards: Array<{
  key: MetricMode
  icon: string
  title: string
  unit: string
  tone: string
  read: (latest: SensorReading | null) => string
}> = [
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
  },
  {
    key: 'light',
    icon: 'lx',
    title: '光照',
    unit: 'Lux',
    tone: 'amber',
    read: (latest) => `${fmt(latest?.lightIntensity, 0)} Lux`
  }
]
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
