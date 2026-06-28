export type SensorReading = {
  id: number | null
  deviceId: string
  nodeId: number
  temperature: number
  humidity: number
  lightIntensity: number
  recordTime: string
}

export type SensorTrendPoint = {
  recordTime: string
  temperature: number
  humidity: number
  lightIntensity: number
}

export type SensorSummary = {
  latest: SensorReading | null
  totalCount: number
}

export type PointCloudRecord = {
  id: number
  recordTime: string
  fileName: string
  url: string
  fileExists: boolean
}

export type TrendMode = 'realtime' | 'hour' | 'day' | 'week'
export type MetricMode = 'all' | 'temperature' | 'humidity' | 'light'

export type ServiceStatus = {
  name: string
  running: boolean
  detail: string
}

export type SystemStatus = {
  healthy: boolean
  checkedAt: string
  api: ServiceStatus
  database: ServiceStatus
  collector: ServiceStatus
  pointCloudDirectory: ServiceStatus
}
