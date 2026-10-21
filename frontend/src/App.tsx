import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type ComponentScore = { score: number | null; weight: number }
type Station = {
  station_id: string
  name: string
  city: string
  connector_count: number
  power_kw: number
  business_importance: { level: string; score: number }
  health: {
    score: number | null
    status: 'scored' | 'insufficient_data'
    components: Record<string, ComponentScore>
    data_gaps: string[]
    recurring_fault_codes: string[]
    recurring_fault_days: number
  }
  data_classification: string
  history?: Array<{
    date: string
    available_minutes: number | null
    eligible_minutes: number
    start_attempts: number
    successful_starts: number
    fault_codes: string[]
  }>
  maintenance_records?: Array<{ date: string; type: string; summary: string; source: string }>
  safety_reports?: Array<{ date: string; label: string; summary: string }>
}
type Citation = { title: string; url?: string; excerpt?: string }
type Message = {
  role: 'assistant' | 'user'
  content: string
  citations?: Citation[]
  knowledgeRetrieved?: boolean
  error?: boolean
}
type ServiceStatus = {
  status: string
  data_classification: string
  snapshot_at: string
  foundry_agent_configured: boolean
  foundry_iq_configured: boolean
}

const API = '/api'
const componentLabels: Record<string, string> = {
  availability: 'Availability',
  charging_success: 'Charge success',
  recurring_faults: 'Recurring faults',
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json() as Promise<T>
}

async function fetchDashboard() {
  return Promise.all([
    getJson<ServiceStatus>('/health'),
    getJson<{ stations: Station[] }>('/stations'),
  ])
}

function scoreLabel(score: number | null) {
  if (score === null) return 'Insufficient data'
  if (score >= 90) return 'Healthy'
  if (score >= 75) return 'Watch'
  return 'Needs attention'
}

function Sparkline({ history }: { history: NonNullable<Station['history']> }) {
  const points = history
    .map((day, index) => ({
      x: 4 + (index * 292) / Math.max(history.length - 1, 1),
      y: day.available_minutes === null
        ? null
        : 55 - (day.available_minutes / Math.max(day.eligible_minutes, 1)) * 45,
    }))
    .filter((point): point is { x: number; y: number } => point.y !== null)
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  return (
    <svg className="trend-chart" viewBox="0 0 300 64" role="img" aria-label="Daily availability over the past 30 days">
      <path className="chart-grid" d="M4 10H296 M4 32H296 M4 54H296" />
      {path && <path className="chart-line" d={path} />}
      {points.length > 0 && <circle className="chart-dot" cx={points.at(-1)?.x} cy={points.at(-1)?.y} r="3" />}
    </svg>
  )
}

function App() {
  const [stations, setStations] = useState<Station[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<Station | null>(null)
  const [service, setService] = useState<ServiceStatus | null>(null)
  const [loadError, setLoadError] = useState('')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('All stations')
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const chatAbortController = useRef<AbortController | null>(null)
  const chatRequestSequence = useRef(0)

  const loadStations = async () => {
    try {
      const [health, result] = await fetchDashboard()
      setService(health)
      setStations(result.stations)
      setLoadError('')
      setSelectedId((current) => current || result.stations[0]?.station_id || '')
    } catch {
      setLoadError('We could not reach the Asset Health API. No local or canned station data is being substituted.')
    }
  }

  useEffect(() => {
    let active = true
    fetchDashboard()
      .then(([health, result]) => {
        if (!active) return
        setService(health)
        setStations(result.stations)
        setSelectedId(result.stations[0]?.station_id || '')
      })
      .catch(() => {
        if (active) setLoadError('We could not reach the Asset Health API. No local or canned station data is being substituted.')
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selectedId) return
    chatAbortController.current?.abort()
    let active = true
    getJson<Station>(`/stations/${selectedId}`)
      .then((station) => {
        if (active) setDetail(station)
      })
      .catch(() => {
        if (active) setLoadError('Station details could not be loaded from the API.')
      })
    return () => {
      active = false
    }
  }, [selectedId])

  const filteredStations = useMemo(() => {
    const search = query.trim().toLowerCase()
    return stations.filter((station) => {
      const matchesQuery = !search || `${station.station_id} ${station.name} ${station.city}`.toLowerCase().includes(search)
      const matchesFilter = filter === 'All stations'
        || (filter === 'Needs attention' && (station.health.score === null || station.health.score < 75))
        || (filter === 'High importance' && station.business_importance.score >= 70)
      return matchesQuery && matchesFilter
    })
  }, [filter, query, stations])

  const scored = stations.filter((station) => station.health.score !== null)
  const averageScore = scored.length
    ? Math.round(scored.reduce((sum, station) => sum + (station.health.score ?? 0), 0) / scored.length)
    : null
  const attentionCount = stations.filter((station) => station.health.score === null || station.health.score < 75).length

  const sendQuestion = async (event: FormEvent) => {
    event.preventDefault()
    const text = question.trim()
    if (!text || !selectedId || chatBusy) return
    const stationId = selectedId
    const requestSequence = ++chatRequestSequence.current
    const controller = new AbortController()
    chatAbortController.current = controller
    setMessages((current) => [...current, { role: 'user', content: text }])
    setQuestion('')
    setChatBusy(true)
    try {
      const response = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ station_id: stationId, question: text }),
        signal: controller.signal,
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`)
      if (requestSequence !== chatRequestSequence.current) return
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: result.answer,
          citations: result.citations ?? [],
          knowledgeRetrieved: result.knowledge_retrieved === true,
        },
      ])
    } catch (error) {
      if (controller.signal.aborted || requestSequence !== chatRequestSequence.current) return
      const message = error instanceof Error ? error.message : 'The Foundry investigation failed.'
      setMessages((current) => [...current, { role: 'assistant', content: message, error: true }])
    } finally {
      if (requestSequence === chatRequestSequence.current) {
        chatAbortController.current = null
        setChatBusy(false)
      }
    }
  }

  const selectedDetail = detail?.station_id === selectedId ? detail : null
  const insufficientStations = filteredStations.filter((station) => station.health.score === null)
  const scoredStations = filteredStations.filter((station) => station.health.score !== null)
  const renderStationRow = (station: Station) => (
    <button
      key={station.station_id}
      className={`station-row ${selectedId === station.station_id ? 'selected' : ''}`}
      onClick={() => {
        if (selectedId !== station.station_id) {
          chatRequestSequence.current += 1
          chatAbortController.current?.abort()
          setChatBusy(false)
          setSelectedId(station.station_id)
          setDetail(null)
        }
        setMessages([])
      }}
    >
      <span className={`score-dot ${station.health.score === null ? 'score-na' : station.health.score < 75 ? 'score-low' : station.health.score < 90 ? 'score-mid' : 'score-good'}`}>
        {station.health.score ?? '—'}
      </span>
      <span className="station-main"><strong>{station.name}</strong><small>{station.station_id} <span>·</span> {station.city}</small></span>
      <span className={`importance importance-${station.business_importance.level.toLowerCase()}`}>{station.business_importance.level}</span>
      <span className="row-chevron">›</span>
    </button>
  )

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Northstar Asset Health home">
          <span className="brand-mark">N</span>
          <span>northstar<span className="brand-sub">ASSET HEALTH</span></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <button className="nav-item active"><span className="nav-icon">◫</span> Fleet overview</button>
        <button className="nav-item" onClick={() => setFilter('High importance')}><span className="nav-icon">⌖</span> Priority sites</button>
        <div className="sidebar-label source-label">DATA SOURCES</div>
        <div className="source-row"><span className="status-led mock-led" /> Station telemetry <span className="source-tag">MOCK</span></div>
        <div className="source-row"><span className="status-led mock-led" /> Work orders <span className="source-tag">MOCK</span></div>
        <div className="source-row"><span className={`status-led ${service?.foundry_iq_configured ? 'online-led' : 'offline-led'}`} /> Foundry IQ <span className="source-tag">{service?.foundry_iq_configured ? 'READY' : 'SETUP'}</span></div>
        <div className="sidebar-bottom">
          <div className="avatar">AH</div>
          <div><strong>Asset operations</strong><span>PoC workspace</span></div>
          <span className="more">···</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Operations <span>/</span> <strong>Fleet overview</strong></div>
          <div className="topbar-right">
            <span className="snapshot-label"><span className="status-led mock-led" /> STATIC SNAPSHOT</span>
            <button className="icon-button" aria-label="Refresh fleet data" onClick={() => void loadStations()}>↻</button>
            <div className="user-avatar">A</div>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">FLEET INTELLIGENCE <span className="pill mock-pill">MOCK DATA</span></p>
              <h1>Asset health</h1>
              <p className="subheading">A clearer view of what needs attention — and why.</p>
            </div>
            <button className="export-button" onClick={() => window.print()}><span>↧</span> Export view</button>
          </section>

          {loadError && (
            <div className="notice error-notice" role="alert">
              <span>{loadError}</span><button onClick={() => void loadStations()}>Retry</button>
            </div>
          )}
          <div className="notice snapshot-notice">
            <span className="notice-icon">i</span>
            <span><strong>Fixed demo snapshot.</strong> This experience uses fictional data, not live charger telemetry or maintenance records.</span>
            <span className="notice-date">{service?.snapshot_at ? new Date(service.snapshot_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }) : '—'}</span>
          </div>

          <section className="metric-grid" aria-label="Fleet summary">
            <div className="metric-card"><span className="metric-icon teal">◉</span><div className="metric-title">Stations monitored</div><div className="metric-value">{stations.length || '—'}<small> stations</small></div><div className="metric-foot">Across {new Set(stations.map((station) => station.city)).size || '—'} demo cities</div></div>
            <div className="metric-card"><span className="metric-icon amber">⌁</span><div className="metric-title">Need attention</div><div className="metric-value">{stations.length ? attentionCount : '—'}<small> stations</small></div><div className="metric-foot"><span className="dot-amber" /> Low score or incomplete evidence</div></div>
            <div className="metric-card"><span className="metric-icon blue">◌</span><div className="metric-title">Average health</div><div className="metric-value">{averageScore ?? '—'}<small> / 100</small></div><div className="metric-foot">Weighted operational indicators</div></div>
            <div className="metric-card"><span className="metric-icon violet">⌖</span><div className="metric-title">Critical importance</div><div className="metric-value">{stations.length ? stations.filter((station) => station.business_importance.score >= 70).length : '—'}<small> sites</small></div><div className="metric-foot">Business priority is separate</div></div>
          </section>

          <section className="workspace-grid">
            <div className="fleet-panel panel">
              <div className="panel-heading">
                <div><h2>Station portfolio</h2><p>Ranked by health score, with business importance alongside.</p></div>
                <button className="subtle-button" onClick={() => void loadStations()}>↻ <span>Refresh</span></button>
              </div>
              <div className="portfolio-toolbar">
                <label className="search-box"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search station or city" /></label>
                <select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter stations">
                  <option>All stations</option><option>Needs attention</option><option>High importance</option>
                </select>
              </div>
              <div className="station-list">
                {insufficientStations.length > 0 && <div className="station-group-label">Insufficient data <span>{insufficientStations.length}</span></div>}
                {insufficientStations.map(renderStationRow)}
                {scoredStations.length > 0 && <div className="station-group-label">Scored stations · lowest first <span>{scoredStations.length}</span></div>}
                {scoredStations.map(renderStationRow)}
                {filteredStations.length === 0 && <p className="empty-list">No stations match this filter.</p>}
              </div>
              <div className="list-footer">{filteredStations.length} stations <span>Sorted by lowest health first</span></div>
            </div>

            <div className="detail-panel panel">
              {!selectedDetail && !loadError && <div className="loading-state">Loading station details…</div>}
              {selectedDetail && (
                <>
                  <div className="detail-heading">
                    <div><p className="eyebrow">{selectedDetail.station_id} <span>·</span> {selectedDetail.city.toUpperCase()}</p><h2>{selectedDetail.name}</h2></div>
                    <span className={`health-status ${selectedDetail.health.status === 'scored' ? 'status-scored' : 'status-missing'}`}>{scoreLabel(selectedDetail.health.score)}</span>
                  </div>
                  <div className="detail-overview">
                    <div className="score-large">{selectedDetail.health.score ?? '—'}<span>{selectedDetail.health.score === null ? '' : '/100'}</span></div>
                    <div className="score-copy"><strong>Operational health score</strong><span>Last 30 days <i>·</i> transparent weighted score</span></div>
                    <div className="business-score"><span>BUSINESS IMPORTANCE</span><strong>{selectedDetail.business_importance.level}</strong><small>{selectedDetail.business_importance.score}/100 impact</small></div>
                  </div>
                  <div className="trend-heading"><strong>Availability trend</strong><span>30 DAYS</span></div>
                  {selectedDetail.history && <Sparkline history={selectedDetail.history} />}
                  <div className="axis-labels"><span>21 Sep</span><span>06 Oct</span><span>20 Oct</span></div>
                  <div className="component-heading"><strong>Health components</strong><button title="40% availability, 40% charge success, 20% recurring-fault days">ⓘ Scoring rules</button></div>
                  <div className="component-list">
                    {Object.entries(selectedDetail.health.components).map(([key, component]) => (
                      <div className="component-row" key={key}>
                        <div className="component-name"><span>{componentLabels[key]}</span><small>{Math.round(component.weight * 100)}% weight</small></div>
                        <div className="component-track"><span style={{ width: `${component.score ?? 0}%` }} /></div>
                        <strong>{component.score === null ? '—' : `${component.score}`}</strong>
                      </div>
                    ))}
                  </div>
                  {selectedDetail.health.data_gaps.length > 0 && <div className="data-gap">{selectedDetail.health.data_gaps.join(' ')}</div>}
                  {selectedDetail.safety_reports?.map((report) => (
                    <div className="safety-flag" key={report.date}><strong>Human review required</strong><span>{report.summary}</span></div>
                  ))}
                  <div className="maintenance-heading"><strong>Recent maintenance</strong><span>MOCK RECORDS</span></div>
                  {selectedDetail.maintenance_records?.slice(0, 2).map((record) => (
                    <div className="maintenance-row" key={`${record.date}-${record.type}`}><span className="maintenance-icon">✓</span><span><strong>{record.type}</strong><small>{record.summary}</small></span><time>{new Date(`${record.date}T00:00:00Z`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' })}</time></div>
                  ))}
                  <p className="detail-disclaimer">Fictional PoC records · not connected to a work-order system</p>
                </>
              )}
            </div>
          </section>

          <section className="assistant-panel panel">
            <div className="assistant-intro">
              <div className="assistant-icon">✳</div>
              <div><h2>Asset Health investigator</h2><p>Ask a question about this station. Answers use station evidence and Foundry IQ reference knowledge.</p></div>
              <div className={`agent-state ${service?.foundry_agent_configured && service?.foundry_iq_configured ? 'agent-ready' : ''}`}><span className="status-led" />{service?.foundry_agent_configured && service?.foundry_iq_configured ? 'FOUNDRY CONNECTED' : 'FOUNDRY SETUP REQUIRED'}</div>
            </div>
            <div className="chat-body">
              {messages.length === 0 && (
                <div className="chat-empty">
                  <span className="sparkle">✦</span>
                  <strong>Investigate with evidence</strong>
                  <span>Try “What is driving this score?” or “What should an operator check next?”</span>
                </div>
              )}
              {messages.map((message, index) => (
                <div className={`chat-message ${message.role} ${message.error ? 'message-error' : ''}`} key={`${index}-${message.role}`}>
                  <span className="message-avatar">{message.role === 'assistant' ? '✳' : 'A'}</span>
                  <div className="message-content"><span className="message-label">{message.role === 'assistant' ? 'INVESTIGATOR' : 'YOU'}</span><p>{message.content}</p>
                    {message.role === 'assistant' && !message.error && <small className="knowledge-status">{message.knowledgeRetrieved ? 'Foundry IQ knowledge was retrieved' : 'No Foundry IQ retrieval was reported for this answer'}</small>}
                    {message.citations && message.citations.length > 0 && (
                      <div className="citations"><strong>Sources</strong>{message.citations.map((citation, citationIndex) => <a key={`${citation.title}-${citationIndex}`} href={citation.url || '#'} target={citation.url ? '_blank' : undefined} rel={citation.url ? 'noreferrer' : undefined}>{citation.title}{citation.excerpt && <small>{citation.excerpt}</small>}</a>)}</div>
                    )}
                  </div>
                </div>
              ))}
              {chatBusy && <div className="chat-loading"><span className="loading-pulse" /> Foundry agent is reviewing station evidence and knowledge sources…</div>}
            </div>
            <form className="chat-form" onSubmit={sendQuestion}>
              <input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1500} placeholder={selectedId ? `Ask about ${selectedId}…` : 'Select a station to ask a question'} disabled={!selectedId || chatBusy} />
              <span className="chat-scope">Context: {selectedId || 'none'}</span>
              <button type="submit" disabled={!question.trim() || chatBusy || !selectedId} aria-label="Send question">↑</button>
            </form>
            <div className="assistant-disclaimer"><span>ⓘ</span> Decision support only. Confirm operational actions with your team. No live charger control.</div>
          </section>

          <footer className="page-footer"><span>Northstar Asset Health <i>·</i> PoC 0.1</span><span>MOCK DATA <i>·</i> NOT FOR OPERATIONAL USE</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App
