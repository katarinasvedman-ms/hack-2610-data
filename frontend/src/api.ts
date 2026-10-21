export type ComponentScore = {
  weight: number
  score: number | null
  contribution: number | null
  coverage: string
}

export type HealthRow = {
  station_id: string
  classification: 'MOCK'
  snapshot_at: string
  window_days: number
  health_score: number | null
  status: 'scored' | 'insufficient_data'
  components: Record<'availability' | 'charging_success' | 'station_faults', ComponentScore>
  importance: number
  importance_explanation: string
  safety_escalation: boolean
}

export type SnapshotResponse = {
  classification: 'MOCK'
  snapshot_at: string
  window_days: number
  stations: HealthRow[]
}

export type ServiceStatus = {
  auth_required: boolean
  foundry_configured: boolean
}

export type StationDetail = {
  station: {
    station_id: string
    site_name: string
    region: string
    classification: 'MOCK'
    connectors: { connector_id: string; rated_kw: number; state: string }[]
  }
  health: HealthRow
  maintenance: MaintenanceRecord[]
}

export type HistoryDay = {
  date: string
  eligible_minutes: number | null
  available_minutes: number | null
  attempts: { successful_starts: number | null; failed_starts: number | null }
  faults: { fault_id: string; occurred_at: string; code: string; category: string; description: string }[] | null
}

export type MaintenanceRecord = {
  record_id: string
  station_id: string
  occurred_at: string
  status: string
  summary: string
  connector_id: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const getHealth = (sort: string, importance: string) =>
  request<SnapshotResponse>(`/api/health?sort=${sort}${importance ? `&importance=${importance}` : ''}`)

export const getStatus = () => request<ServiceStatus>('/api/status')

export const getStation = (id: string) => request<StationDetail>(`/api/stations/${encodeURIComponent(id)}`)

export const getHistory = (id: string) =>
  request<{ days: HistoryDay[] }>(`/api/stations/${encodeURIComponent(id)}/history`)

export type ChatResult = {
  conversation_id: string
  answer: string
  activity: { type: string; status: string; tool?: string }[]
  citations: {
    title: string
    url?: string
    section?: string
    page?: string | number
    source?: string
    version?: string
    date?: string
  }[]
  operational_references: { source: string; record_type: string; record_id: string; classification: string }[]
  notice: string
}

export const askInvestigator = (message: string, conversationId?: string, stationId?: string) =>
  request<ChatResult>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      station_id: stationId,
    }),
  })
