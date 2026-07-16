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

export type GreenhouseReading = {
  id: number | null
  plcId: string
  temperature: number | null
  humidity: number | null
  co2: number | null
  lightOn: boolean | null
  recordTime: string
}

export type GreenhouseTrendPoint = {
  recordTime: string
  temperature: number | null
  humidity: number | null
  co2: number | null
  lightOn: number | null
}

export type GreenhouseSummary = {
  latest: GreenhouseReading | null
  totalCount: number
}

export type GreenhouseAlarmEvent = {
  id: number
  plcId: string
  alarmCode: string
  alarmName: string
  message: string
  active: boolean
  acknowledged: boolean
  startedAt: string
  clearedAt: string | null
}

export type GreenhouseRealtimeState = {
  connected: boolean
  plc_ip: string
  connection_error: string | null
  time_text: string
  measurements: Record<string, number | null>
  targets: Record<string, number | null>
  feedback: Record<string, number | null>
  run_status: Record<string, boolean>
  run_status_labels: Record<string, string>
  controls: Record<string, boolean>
  control_labels: Record<string, string>
  alarms: Record<string, { active: boolean; acknowledged?: boolean }>
  alarm_events: Array<{
    id: number
    name: string
    label: string
    message: string
    active: boolean
    acknowledged: boolean
    time: string
    cleared_at: string | null
  }>
  active_alarm_count: number
  unacknowledged_alarm_count: number
  curves?: Record<string, GreenhouseCurvePlan>
  curve_traces?: Record<string, GreenhouseCurvePlan>
  interlocks?: Record<string, { blocked: boolean; reason: string | null }>
}

export type GreenhouseTargetsUpdate = {
  temperature?: number
  humidity?: number
  co2?: number
  light?: boolean
}

export type GreenhouseView = 'operations' | 'curves' | 'history' | 'alarms'

export type GreenhouseCurveRequest = {
  sensor: 'temperature' | 'humidity' | 'co2'
  start_value: number
  end_value: number
  duration_seconds: number
  interval_seconds: number
  shape: 'linear' | 'smooth' | 'step'
}

export type GreenhouseCurvePlan = GreenhouseCurveRequest & {
  status: string
  progress: number
  remaining_seconds: number
  start_timestamp: number
  end_timestamp: number
}

export type GreenhouseHistorySensor = 'temperature' | 'humidity' | 'co2' | 'light'

export type GreenhouseHistoryQuery = {
  start_timestamp: number
  end_timestamp: number
  interval_seconds: number
  sensors: GreenhouseHistorySensor[]
  limit: number
}

export type GreenhouseHistoryRow = {
  timestamp: number
  time_text: string
  temperature?: number | null
  humidity?: number | null
  co2?: number | null
  light?: number | null
  target_temperature?: number | null
  target_humidity?: number | null
  target_co2?: number | null
  target_light_on?: number | null
}

export type GreenhouseHistoryResult = {
  start_timestamp: number
  end_timestamp: number
  start_time_text: string
  end_time_text: string
  interval_seconds: number
  sensors: GreenhouseHistorySensor[]
  raw_count: number
  sampled_count: number
  returned_count: number
  truncated: boolean
  rows: GreenhouseHistoryRow[]
  statistics: Record<string, unknown>
}

export type EnvironmentReading = {
  id: number | null
  sourceId: string
  temperature: number | null
  humidity: number | null
  lightIntensity?: number | null
  co2?: number | null
  lightOn?: boolean | null
  recordTime: string
}

export type EnvironmentTrendPoint = {
  recordTime: string
  temperature: number | null
  targetTemperature?: number | null
  humidity: number | null
  lightIntensity?: number | null
  co2?: number | null
  lightOn?: number | null
}

export type EnvironmentSummary = {
  latest: EnvironmentReading | null
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
export type DataSource = 'sensor' | 'greenhouse'
export type MetricMode = 'all' | 'temperature' | 'humidity' | 'co2' | 'light'

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
