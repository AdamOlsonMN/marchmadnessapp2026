import { useState, useEffect, useCallback } from 'react'
import BracketESPN from './components/BracketESPN'
import OddsTable from './components/OddsTable'
import ModelPicks from './components/ModelPicks'
import ExportPicks from './components/ExportPicks'
import AdamsPicks from './components/AdamsPicks'
import './App.css'

// Same-origin /api in dev (Vite proxy) and production (reverse proxy). Override with VITE_API_URL when needed.
const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

function App() {
  const [bracket, setBracket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [fixedWinners, setFixedWinners] = useState({})
  const [whatifOdds, setWhatifOdds] = useState(null)
  const [whatifLoading, setWhatifLoading] = useState(false)
  const [historyUpsets, setHistoryUpsets] = useState(null)
  const [valueRecs, setValueRecs] = useState(null)
  const [valueLoading, setValueLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('bracket')
  const [oddsSort, setOddsSort] = useState({ key: 'champ', dir: 'desc' })

  useEffect(() => {
    fetch(`${API_BASE}/bracket`)
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText || 'Failed to load bracket')
        return res.json()
      })
      .then(setBracket)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/history/upsets`)
      .then((res) => res.ok ? res.json() : null)
      .then((data) => data?.matchups && setHistoryUpsets(data.matchups))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (activeTab === 'value') {
      setValueLoading(true)
      fetch(`${API_BASE}/value?threshold=0.05`)
        .then((res) => res.ok ? res.json() : { recommendations: [] })
        .then((data) => setValueRecs(data.recommendations || []))
        .catch(() => setValueRecs([]))
        .finally(() => setValueLoading(false))
    }
  }, [activeTab])

  useEffect(() => {
    if (!bracket || Object.keys(fixedWinners).length === 0) {
      setWhatifOdds(null)
      return
    }
    setWhatifLoading(true)
    fetch(`${API_BASE}/whatif`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fixed_winners: fixedWinners }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText || 'What-if failed')
        return res.json()
      })
      .then(setWhatifOdds)
      .catch(() => setWhatifOdds(null))
      .finally(() => setWhatifLoading(false))
  }, [bracket, fixedWinners])

  const handleLock = useCallback((slot, teamId) => {
    setFixedWinners((prev) => ({ ...prev, [slot]: teamId }))
  }, [])

  const handleUnlock = useCallback((slot) => {
    setFixedWinners((prev) => {
      const next = { ...prev }
      delete next[slot]
      return next
    })
  }, [])

  const clearPicks = useCallback(() => setFixedWinners({}), [])

  if (loading) return <div className="app-loading">Loading bracket…</div>
  if (error) return <div className="app-error">Error: {error}</div>
  if (!bracket) return null

  const teamsById = Object.fromEntries((bracket.teams || []).map((t) => [t.id, t]))
  const teamName = (id) => teamsById[id]?.name ?? `Team ${id}`

  const championOdds = whatifOdds?.championOdds ?? bracket.championOdds ?? {}
  const advancement = whatifOdds?.advancement ?? bracket.advancement ?? {}
  const lockedCount = Object.keys(fixedWinners).length

  return (
    <div className="app command-center">
      <header className="app-header">
        <div className="header-brand">
          <span className="header-label">Command Center</span>
          <h1>Bracket</h1>
        </div>
        <div className="header-badges">
          {bracket.modelInfo && (
            <span className="badge badge-model">{bracket.modelInfo}</span>
          )}
          {lockedCount > 0 && (
            <span className="badge badge-whatif">
              What-if: {lockedCount} locked
              <button type="button" className="btn-clear" onClick={clearPicks} aria-label="Clear picks">×</button>
            </span>
          )}
        </div>
      </header>
      <nav className="app-tabs" aria-label="Data views">
        {[
          { id: 'bracket', label: 'Bracket' },
          { id: 'champion', label: 'Champion odds' },
          { id: 'advancement', label: 'Advancement' },
          { id: 'picks', label: '2026 picks' },
          { id: 'adams', label: "Adam's picks" },
          { id: 'value', label: 'Best values' },
        ].map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`tab ${activeTab === id ? 'tab-active' : ''}`}
            onClick={() => setActiveTab(id)}
            aria-selected={activeTab === id}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="app-main">
        {activeTab === 'bracket' && (
          <>
            <section className="bracket-hero">
              <BracketESPN
                games={bracket.games}
                teams={bracket.teams}
                slotOrder={bracket.slotOrder}
                slotTree={bracket.slotTree}
                fixedWinners={fixedWinners}
                nextGameProbs={bracket.nextGameProbs}
                onLock={handleLock}
                onUnlock={handleUnlock}
              />
            </section>
            <aside className="odds-panel">
              {whatifLoading && <p className="odds-loading">Updating odds…</p>}
              {championOdds && Object.keys(championOdds).length > 0 && (
                <section className="champion-odds">
                  <h2>Champion odds</h2>
                  <ul>
                    {Object.entries(championOdds)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 10)
                      .map(([tid, p]) => (
                        <li key={tid}>
                          <span>{teamName(Number(tid))}</span>
                          <span className="pct">{(p * 100).toFixed(1)}%</span>
                        </li>
                      ))}
                  </ul>
                </section>
              )}
              {advancement?.final4 && Object.keys(advancement.final4).length > 0 && (
                <section className="advancement-odds">
                  <h2>Final Four</h2>
                  <ul>
                    {Object.entries(advancement.final4)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 5)
                      .map(([tid, p]) => (
                        <li key={tid}>
                          <span>{teamName(Number(tid))}</span>
                          <span className="pct">{(p * 100).toFixed(1)}%</span>
                        </li>
                      ))}
                  </ul>
                </section>
              )}
              {historyUpsets && historyUpsets.length > 0 && (
                <section className="history-upsets">
                  <h2>Historical upsets</h2>
                  <p className="history-upsets-desc">Upset rate by seed matchup</p>
                  <ul>
                    {historyUpsets.slice(0, 8).map((m) => (
                      <li key={m.seed_matchup}>
                        <strong>{m.seed_matchup}</strong>: {m.upset_rate_pct}% ({m.upsets}/{m.games})
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </aside>
          </>
        )}
        {activeTab === 'champion' && (
          <div className="tab-content tab-content-full">
            <h2>Tournament odds</h2>
            <p className="tab-meta">
              Full bracket simulation (10k runs). Probability each team reaches each round or wins the title. {bracket.modelInfo}
            </p>
            <OddsTable
              teams={bracket.teams || []}
              championOdds={championOdds}
              advancement={advancement}
              teamName={teamName}
              sort={oddsSort}
              onSort={setOddsSort}
            />
          </div>
        )}
        {activeTab === 'advancement' && (
          <div className="tab-content tab-content-full">
            <h2>Advancement odds</h2>
            <p className="tab-meta">Probability to reach each round (model)</p>
            <div className="advancement-grid">
              {['final4', 'elite8', 'sweet16', 'r2'].map((key) => (
                advancement[key] && Object.keys(advancement[key]).length > 0 && (
                  <section key={key} className="advancement-section">
                    <h3>{key === 'r2' ? 'Round 2' : key.replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase()).trim()}</h3>
                    <ul className="data-list">
                      {Object.entries(advancement[key])
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 8)
                        .map(([tid, p]) => (
                          <li key={tid}>
                            <span className="name">{teamName(Number(tid))}</span>
                            <span className="pct">{(p * 100).toFixed(1)}%</span>
                          </li>
                        ))}
                    </ul>
                  </section>
                )
              ))}
            </div>
            {(!advancement.final4 || Object.keys(advancement.final4).length === 0) && (
              <p className="tab-empty">Run the bracket with all 32 R1 games for advancement odds.</p>
            )}
          </div>
        )}
        {activeTab === 'picks' && (
          <div className="tab-content tab-content-full picks-tab-export">
            <h2>2026 picks</h2>
            <p className="tab-meta">Model picks for each game (higher win probability). {bracket.modelInfo}</p>
            <ExportPicks games={bracket.games || []} teamName={teamName} />
            <ModelPicks
              games={bracket.games || []}
              teams={bracket.teams || []}
              teamName={teamName}
              pickSummary={bracket.pickSummary || null}
            />
          </div>
        )}
        {activeTab === 'adams' && (
          <div className="tab-content tab-content-full">
            <h2>Adam&apos;s picks</h2>
            <AdamsPicks games={bracket.games || []} teamName={teamName} />
          </div>
        )}
        {activeTab === 'value' && (
          <div className="tab-content tab-content-full">
            <h2>Best values</h2>
            <p className="tab-meta">Games where model disagrees with market (edge ≥ 5%). Add odds data to see recommendations.</p>
            {valueLoading && <p className="tab-meta">Loading…</p>}
            {!valueLoading && valueRecs && valueRecs.length === 0 && (
              <p className="tab-empty">No value recommendations. Add data/raw/overtime_odds.json or CSV and ensure team names match.</p>
            )}
            {!valueLoading && valueRecs && valueRecs.length > 0 && (
              <ul className="data-list value-list">
                {valueRecs.map((r, i) => (
                  <li key={i}>
                    <span className="matchup">{r.team1} vs {r.team2}</span>
                    <span className="pick">{r.model_pick}</span>
                    <span className="pct">{(r.model_prob * 100).toFixed(0)}%</span>
                    <span className="edge">edge {(r.edge * 100).toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      <footer className="app-footer">
        <span className="footer-dot" aria-hidden /> Live model
        <span className="footer-sep">·</span>
        Click a team to lock winner and run what-if
      </footer>
    </div>
  )
}

export default App
