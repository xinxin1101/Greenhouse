import axios from 'axios'
import type {
  DataSource,
  EnvironmentSummary,
  EnvironmentTrendPoint,
  GreenhouseAlarmEvent,
  GreenhouseCurveRequest,
  GreenhouseHistoryQuery,
  GreenhouseHistoryResult,
  GreenhouseRealtimeState,
  GreenhouseSummary,
  GreenhouseTrendPoint,
  GreenhouseTargetsUpdate,
  PointCloudRecord,
  SensorSummary,
  SensorTrendPoint,
  SystemStatus,
  TrendMode
} from '../types/sensor'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000
})

export async function fetchSummary(source: DataSource): Promise<EnvironmentSummary> {
  if (source === 'greenhouse') {
    const { data } = await http.get<GreenhouseSummary>('/greenhouse/summary')
    return {
      totalCount: data.totalCount,
      latest: data.latest
        ? {
            id: data.latest.id,
            sourceId: data.latest.plcId,
            temperature: data.latest.temperature,
            humidity: data.latest.humidity,
            co2: data.latest.co2,
            lightOn: data.latest.lightOn,
            recordTime: data.latest.recordTime
          }
        : null
    }
  }

  const { data } = await http.get<SensorSummary>('/sensor/summary')
  return {
    totalCount: data.totalCount,
    latest: data.latest
      ? {
          id: data.latest.id,
          sourceId: data.latest.deviceId,
          temperature: data.latest.temperature,
          humidity: data.latest.humidity,
          lightIntensity: data.latest.lightIntensity,
          recordTime: data.latest.recordTime
        }
      : null
  }
}

export async function fetchTrend(source: DataSource, params: {
  mode: TrendMode
  start?: string
  end?: string
  limit?: number
}): Promise<EnvironmentTrendPoint[]> {
  if (source === 'greenhouse') {
    const { data } = await http.get<GreenhouseTrendPoint[]>('/greenhouse/trend', { params })
    return data
  }
  const { data } = await http.get<SensorTrendPoint[]>('/sensor/trend', { params })
  return data
}

export async function fetchGreenhouseState() {
  const { data } = await http.get<GreenhouseRealtimeState>('/greenhouse/state')
  return data
}

export async function fetchGreenhouseAlarms(limit = 20) {
  const { data } = await http.get<GreenhouseAlarmEvent[]>('/greenhouse/alarms', {
    params: { limit }
  })
  return data
}

export async function updateGreenhouseTargets(payload: GreenhouseTargetsUpdate) {
  const { data } = await http.post('/greenhouse/targets', payload)
  return data
}

export async function updateGreenhouseControl(device: 'system' | 'compressor' | 'uv' | 'co2', state: boolean) {
  const { data } = await http.post('/greenhouse/control', { device, state })
  return data
}

export async function updateGreenhouseFan(state: boolean) {
  const { data } = await http.post('/greenhouse/fan', { state })
  return data
}

export async function acknowledgeGreenhouseAlarms() {
  const { data } = await http.post('/greenhouse/alarms/ack')
  return data
}

export async function acknowledgeAllGreenhouseAlarms(plcIds: string[]) {
  const { data } = await http.post('/greenhouse/alarms/ack-all', { plc_ids: plcIds })
  return data
}

export async function acknowledgeGreenhouseAlarm(eventId: number, plcId: string) {
  const { data } = await http.post(`/greenhouse/alarms/${eventId}/ack`, { plc_id: plcId })
  return data
}

export async function startGreenhouseCurve(payload: GreenhouseCurveRequest) {
  const { data } = await http.post('/greenhouse/curves', payload)
  return data
}

export async function fetchGreenhouseCurveTrace(sensor: 'temperature' | 'humidity' | 'co2') {
  const { data } = await http.get(`/greenhouse/curves/${sensor}/trace`, { params: { maxPoints: 1200 } })
  return data
}

export async function cancelGreenhouseCurve(sensor: 'temperature' | 'humidity' | 'co2') {
  const { data } = await http.delete(`/greenhouse/curves/${sensor}`)
  return data
}

export async function fetchGreenhouseHistoryMeta() {
  const { data } = await http.get('/greenhouse/history/meta')
  return data
}

export async function queryGreenhouseHistory(payload: GreenhouseHistoryQuery) {
  const { data } = await http.post<GreenhouseHistoryResult>('/greenhouse/history/query', payload)
  return data
}

export async function exportGreenhouseHistory(payload: GreenhouseHistoryQuery) {
  return http.post('/greenhouse/history/export', payload, { responseType: 'blob' })
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
