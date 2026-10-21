import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  askInvestigator,
  ChatResult,
  getHealth,
  getHistory,
  getStation,
  HealthRow,
  HistoryDay,
  SnapshotResponse,
  StationDetail,
} from './api'
import { formatSnapshot, healthLabel } from './format'

type ChatMessage = { role: 'user' | 'assistant'; text: string; result?: ChatResult }

const componentLabels = {
  availability: 'Availability',
  charging_success: 'Charging success',
  station_faults: 'Recurring station-side faults',
} as const

export default function App() {
  const [snapshot, setSnapshot] = useState<SnapshotResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<StationDetail | null>(null)
  const [history, setHistory] = useState<HistoryDay[]>([])
  const [sort, setSort] = useState('priority')
  const [importance, setImportance] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [detailError, setDetailError] = useState('')
  const [chatError, setChatError] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [conversationId, setConversationId] = useState<string>()
  const [chatLoading, setChatLoading] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    getHealth(sort, importance)
      .then((data) => {
        if (!active) return
        setSnapshot(data)
        setError('')
        if (!selectedId && data.stations.length) setSelectedId(data.stations[0].station_id)
      })
      .catch((reason: Error) => active && setError(reason.message))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [sort, importance])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    setDetail(null)
    setDetailError('')
    Promise.all([getStation(selectedId), getHistory(selectedId)])
      .then(([station, recent]) => {
        if (!active) return
        setDetail(station)
        setHistory(recent.days)
      })
      .catch((reason: Error) => active && setDetailError(reason.message))
    return () => { active = false }
  }, [selectedId])

  const scored = snapshot?.stations.filter((row) => row.health_score !== null) ?? []
  const insufficient = snapshot?.stations.filter((row) => row.health_score === null) ?? []
  const average = useMemo(
    () => scored.length ? Math.round(scored.reduce((total, row) => total + (row.health_score ?? 0), 0) / scored.length) : null,
    [scored],
  )
  const selected = snapshot?.stations.find((row) => row.station_id === selectedId)

  function newConversation(prompt: string) {
    setMessages([])
    setConversationId(undefined)
    setChatError('')
    setQuestion(prompt)
  }

  async function sendMessage(event?: FormEvent, suggested?: string) {
    event?.preventDefault()
    const message = (suggested ?? question).trim()
    if (!message || chatLoading) return
    setMessages((current) => [...current, { role: 'user', text: message }])
    setQuestion('')
    setChatLoading(true)
    setChatError('')
    try {
      const result = await askInvestigator(message, conversationId, selectedId ?? undefined)
      setConversationId(result.conversation_id)
      setMessages((current) => [...current, { role: 'assistant', text: result.answer, result }])
    } catch (reason) {
      setChatError(reason instanceof Error ? reason.message : 'Investigation service unavailable.')
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Fieldnotes home">
          <span className="brand-mark">f</span>
          <span>fieldnotes<span className="brand-dot">.</span></span>
        </a>
        <div className="topbar-right">
          <span className="secure-label"><span className="secure-dot" /> Entra protected</span>
          <span className="avatar">AH</span>
        </div>
      </header>

      <section className="hero">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> OPERATIONS INTELLIGENCE</div>
          <h1>Asset health<span className="title-period">.</span></h1>
          <p className="hero-copy">A clearer view of where to look next.</p>
        </div>
        <div className="snapshot-pill">
          <span className="pulse-dot" />
          <span><strong>MOCK DATA</strong><small>Snapshot · {snapshot ? formatSnapshot(snapshot.snapshot_at) : 'loading'}</small></span>
          <span className="window-chip">30 DAYS</span>
        </div>
      </section>

      <section className="summary-grid" aria-label="Portfolio summary">
        <SummaryCard label="Stations in view" value={String(snapshot?.stations.length ?? '—')} note="Synthetic station inventory" icon="◫" />
        <SummaryCard label="Portfolio health" value={average === null ? '—' : String(average)} suffix={average === null ? '' : '/100'} note="Weighted operational indicators" icon="◒" />
        <SummaryCard label="Needs assessment" value={String(insufficient.length)} note="Insufficient evidence to score" icon="⌁" emphasis={insufficient.length > 0} />
        <SummaryCard label="Escalation flags" value={String(snapshot?.stations.filter((row) => row.safety_escalation).length ?? 0)} note="Separate from health score" icon="!" />
      </section>

      <div className="content-grid">
        <section className="panel station-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow eyebrow-small">FLEET OVERVIEW</div>
              <h2>Stations <span className="count-badge">{snapshot?.stations.length ?? 0}</span></h2>
            </div>
            <div className="filters">
              <label>
                <span className="sr-only">Sort stations</span>
                <select value={sort} onChange={(event) => setSort(event.target.value)}>
                  <option value="priority">Priority order</option>
                  <option value="health">Health: lowest first</option>
                  <option value="importance">Importance first</option>
                </select>
              </label>
              <label>
                <span className="sr-only">Filter by importance</span>
                <select value={importance} onChange={(event) => setImportance(event.target.value)}>
                  <option value="">All importance</option>
                  {[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>Importance {value}</option>)}
                </select>
              </label>
            </div>
          </div>
          {loading && <div className="state-box">Loading the synthetic snapshot…</div>}
          {error && <div className="state-box state-error" role="alert"><strong>Dashboard unavailable</strong><span>{error}</span><button onClick={() => setSort(sort)}>Retry</button></div>}
          {!loading && !error && snapshot && snapshot.stations.length === 0 && <div className="state-box">No stations match these filters.</div>}
          {!loading && !error && (scored.length > 0 || insufficient.length > 0) && (
            <>
              {scored.length > 0 && <div className="station-list">
                {scored.map((row, index) => (
                  <StationRow key={row.station_id} row={row} rank={index + 1} active={row.station_id === selectedId} onClick={() => setSelectedId(row.station_id)} />
                ))}
              </div>}
              {insufficient.length > 0 && (
                <div className="insufficient-group">
                  <div className="group-title"><span>Assessment needed</span><span>{insufficient.length} stations</span></div>
                  {insufficient.map((row) => <StationRow key={row.station_id} row={row} active={row.station_id === selectedId} onClick={() => setSelectedId(row.station_id)} />)}
                </div>
              )}
              <p className="ranking-note">Priority is based on observed health, then business importance. Importance is a separate demo input, not part of the score.</p>
            </>
          )}
        </section>

        <section className="panel detail-panel" aria-live="polite">
          {detailError && <div className="state-box state-error" role="alert"><strong>Station details unavailable</strong><span>{detailError}</span></div>}
          {!detailError && !detail && <div className="state-box">Loading station detail…</div>}
          {detail && selected && <StationDetailView detail={detail} row={selected} history={history} />}
        </section>
      </div>

      <section className="panel investigator-panel">
        <div className="investigator-intro">
          <div className="agent-icon">✳</div>
          <div>
            <div className="eyebrow eyebrow-small">GROUNDED INVESTIGATION</div>
            <h2>Ask the investigator</h2>
            <p>Structured station records and approved reference material, kept distinct.</p>
          </div>
          <span className="agent-status"><span className="secure-dot" /> Foundry agent</span>
        </div>
        <div className="chat-content">
          <div className="chat-messages" aria-live="polite">
            {messages.length === 0 && (
              <div className="chat-empty">
                <p>Explore the evidence. No automatic diagnosis or charger control.</p>
                <div className="suggestions">
                  <button onClick={() => newConversation('Which stations need investigation, and what evidence supports that ranking?')}>Which stations need a closer look?</button>
                  <button onClick={() => newConversation('Explain the score for this station and what evidence is missing.')}>Explain the selected station’s score</button>
                  <button onClick={() => newConversation('What does the PoC scoring guidance say about recurring faults?')}>How are recurring faults treated?</button>
                </div>
              </div>
            )}
            {messages.map((message, index) => (
              <article key={`${index}-${message.role}`} className={`chat-message ${message.role}`}>
                <span className="message-role">{message.role === 'assistant' ? 'INVESTIGATOR' : 'YOU'}</span>
                <p>{message.text}</p>
                {message.result && <MessageSources result={message.result} />}
              </article>
            ))}
            {chatLoading && <div className="agent-thinking"><span className="spinner" /> Checking structured evidence and reference sources…</div>}
            {chatError && <div className="chat-error" role="alert"><strong>Investigation unavailable</strong><span>{chatError}</span><small>The dashboard remains available. No fallback answer was substituted.</small></div>}
          </div>
          <form className="chat-form" onSubmit={sendMessage}>
            <label className="sr-only" htmlFor="question">Ask about station evidence</label>
            <input id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={`Ask about ${selected?.station_id ?? 'station evidence'}…`} maxLength={4000} />
            <button type="submit" disabled={!question.trim() || chatLoading}>Ask <span aria-hidden="true">↗</span></button>
          </form>
          <div className="chat-context">Context handoff: <strong>{selected?.station_id ?? 'none selected'}</strong> · Conversation history stays isolated to the signed-in user.</div>
        </div>
      </section>

      <footer className="footer">
        <span>FIELDNOTES <span className="footer-separator">/</span> ASSET HEALTH PoC</span>
        <span>Illustrative decision support · Not a validated predictor or safety assessment</span>
      </footer>
    </main>
  )
}

function SummaryCard({ label, value, suffix, note, icon, emphasis }: { label: string; value: string; suffix?: string; note: string; icon: string; emphasis?: boolean }) {
  return (
    <article className="summary-card">
      <div className={`summary-icon ${emphasis ? 'icon-warn' : ''}`}>{icon}</div>
      <span className="summary-label">{label}</span>
      <div className={`summary-value ${emphasis ? 'value-warn' : ''}`}>{value}<small>{suffix}</small></div>
      <span className="summary-note">{note}</span>
    </article>
  )
}

function StationRow({ row, rank, active, onClick }: { row: HealthRow; rank?: number; active: boolean; onClick: () => void }) {
  const score = row.health_score
  const tone = score === null ? 'unknown' : score < 65 ? 'low' : score < 85 ? 'medium' : 'high'
  return (
    <button className={`station-row ${active ? 'selected' : ''}`} onClick={onClick} aria-pressed={active}>
      <span className="rank">{rank ? String(rank).padStart(2, '0') : '—'}</span>
      <span className="station-main">
        <strong>{row.station_id}</strong>
        <small>Importance {row.importance} <span>·</span> {row.importance_explanation}</small>
      </span>
      <span className={`health-score score-${tone}`}>{score === null ? '—' : score}<small>{score === null ? 'needs assessment' : '/100'}</small></span>
      <span className={`status-tag tag-${tone}`}>{healthLabel(score)}</span>
      {row.safety_escalation && <span className="escalation" title="Separate safety escalation flag">⚑</span>}
      <span className="row-arrow" aria-hidden="true">→</span>
    </button>
  )
}

function StationDetailView({ detail, row, history }: { detail: StationDetail; row: HealthRow; history: HistoryDay[] }) {
  const latest = history.slice(-14)
  return (
    <div>
      <div className="detail-head">
        <div className="detail-location"><span className="location-icon">⌖</span><span>{detail.station.region} region · {detail.station.site_name}</span></div>
        <div className="detail-title-row">
          <div><h2>{detail.station.station_id}</h2><p>{healthLabel(row.health_score)} <span className="inline-dot">·</span> {detail.station.classification} snapshot</p></div>
          <div className={`detail-score score-${row.health_score === null ? 'unknown' : row.health_score < 65 ? 'low' : row.health_score < 85 ? 'medium' : 'high'}`}>{row.health_score ?? '—'}<small>/100</small></div>
        </div>
        {row.safety_escalation && <div className="safety-banner">⚑ Separate escalation flag · requires the operator’s established safety process</div>}
        <div className="detail-meta">
          <span><strong>{row.importance}/5</strong> business importance</span>
          <span>{detail.station.connectors.length} connectors</span>
          <span>30-day snapshot</span>
        </div>
      </div>

      <div className="section-divider"><span>HEALTH COMPONENTS</span><span>Illustrative · unvalidated</span></div>
      <div className="component-list">
        {Object.entries(row.components).map(([name, component]) => {
          const label = componentLabels[name as keyof typeof componentLabels]
          return (
            <div className="component" key={name}>
              <div className="component-top"><strong>{label}</strong><span>{component.score === null ? 'Insufficient data' : `${component.score.toFixed(1)} / 100`}</span></div>
              <div className="component-meter"><span style={{ width: `${component.score ?? 0}%` }} /></div>
              <div className="component-bottom"><span>{component.weight}% weight · {component.contribution === null ? 'no contribution' : `${component.contribution.toFixed(1)} points`}</span><span>{component.coverage}</span></div>
            </div>
          )
        })}
      </div>

      <div className="section-divider trend-heading"><span>RECENT OPERATIONS</span><span>Daily, last 14 of 30 days</span></div>
      <div className="trend-chart" aria-label="Daily availability trend">
        {latest.map((day) => {
          const percent = day.eligible_minutes && day.available_minutes !== null ? day.available_minutes / day.eligible_minutes * 100 : 0
          return <span key={day.date} title={`${day.date}: ${day.available_minutes === null ? 'missing observation' : `${Math.round(percent)}% available`}`} className={day.available_minutes === null ? 'bar-missing' : ''} style={{ height: `${day.available_minutes === null ? 8 : Math.max(8, percent)}%` }} />
        })}
      </div>
      <div className="chart-legend"><span><i className="legend-green" /> Availability by day</span><span>Missing days shown as gaps</span></div>
      <div className="connector-chips">{detail.station.connectors.map((connector) => <span key={connector.connector_id}>Connector {connector.connector_id} <b>{connector.rated_kw} kW</b> · {connector.state}</span>)}</div>

      <div className="section-divider"><span>FAULT & MAINTENANCE RECORDS</span><span>MOCK only</span></div>
      <div className="record-list">
        {history.flatMap((day) => (day.faults ?? []).map((fault) => ({ ...fault, date: day.date }))).slice(-4).reverse().map((fault) => (
          <div className="record" key={fault.fault_id}>
            <span className={`record-mark ${fault.category === 'station_side' ? 'mark-fault' : 'mark-other'}`} />
            <div><strong>{fault.code}</strong><p>{fault.description}</p><small>{fault.date} · {fault.category === 'station_side' ? 'Station-side event' : 'Authorization / roaming / payment'}</small></div>
          </div>
        ))}
        {detail.maintenance.slice(-3).reverse().map((record) => (
          <div className="record" key={record.record_id}>
            <span className="record-mark mark-maintenance" />
            <div><strong>{record.status === 'open' ? 'Open maintenance record' : 'Maintenance note'}</strong><p>{record.summary}</p><small>{record.record_id} · {new Date(record.occurred_at).toLocaleDateString()}</small></div>
          </div>
        ))}
        {history.every((day) => !day.faults?.length) && detail.maintenance.length === 0 && <p className="empty-records">No synthetic fault or maintenance records in this snapshot.</p>}
      </div>
    </div>
  )
}

function MessageSources({ result }: { result: ChatResult }) {
  return (
    <div className="source-list">
      {result.notice && <small className="mock-notice">{result.notice}</small>}
      {result.citations.map((citation, index) => (
        <a key={`${citation.url}-${index}`} href={citation.url} target="_blank" rel="noopener noreferrer">↗ {citation.title}</a>
      ))}
      {result.operational_references.map((reference, index) => (
        <span key={`${reference.record_id}-${index}`}>▤ {reference.record_id} · {reference.classification}</span>
      ))}
      {result.activity.map((item, index) => (
        <span key={`${item.type}-${index}`} className="activity-pill">{item.type === 'knowledge_retrieval' ? 'Knowledge retrieval' : item.tool?.replaceAll('_', ' ')}</span>
      ))}
    </div>
  )
}
