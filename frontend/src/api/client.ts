import axios from 'axios'
import type { PointCloudRecord, SensorSummary, SensorTrendPoint, SystemStatus, TrendMode } from '../types/sensor'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000
})

export async function fetchSummary() {
  const { data } = await http.get<SensorSummary>('/sensor/summary')
  return data
}

export async function fetchTrend(params: {
  mode: TrendMode
  start?: string
  end?: string
  limit?: number
}) {
  const { data } = await http.get<SensorTrendPoint[]>('/sensor/trend', { params })
  return data
}

export async function fetchPointClouds(params: { start?: string; end?: string }) {
  const { data } = await http.get<PointCloudRecord[]>('/point-cloud/list', { params })
  return data
}

export async function fetchSystemStatus() {
  const { data } = await http.get<SystemStatus>('/system/status')
  return data
}

export function pointCloudFileUrl(record: PointCloudRecord) {
  return record.url
}
