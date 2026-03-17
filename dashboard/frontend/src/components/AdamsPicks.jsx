/**
 * Adam's picks: model picks for the whole tournament, with optional result tracking (correct/incorrect).
 * Results stored in localStorage so you can mark winners as games finish and see how the model did.
 */
import { useMemo, useCallback, useState } from 'react'

const STORAGE_KEY = 'adams_picks_results'
const ROUND_LABELS = { R1: 'Round 1', R2: 'Round 2', R3: 'Sweet 16', R4: 'Elite 8', R5: 'Final Four', R6: 'Championship' }

function loadResults() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveResults(results) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(results))
}

export default function AdamsPicks({ games = [], teamName }) {
  const [results, setResults] = useState(() => loadResults())
  const [editingSlot, setEditingSlot] = useState(null)

  const byRound = useMemo(() => {
    const map = {}
    for (const g of games) {
      const round = (g.slot || '').slice(0, 2) || 'R1'
      if (!map[round]) map[round] = []
      const p1 = g.prob_team1 ?? 0
      const p2 = g.prob_team2 ?? 0
      const pickId = p1 >= p2 ? g.team1_id : g.team2_id
      const pickPct = p1 >= p2 ? p1 : p2
      map[round].push({
        slot: g.slot,
        team1_id: g.team1_id,
        team2_id: g.team2_id,
        team1: g.team1_id != null ? teamName(g.team1_id) : 'TBD',
        team2: g.team2_id != null ? teamName(g.team2_id) : 'TBD',
        seed1: g.seed1,
        seed2: g.seed2,
        pickId,
        pickPct,
        hasPick: g.team1_id != null && g.team2_id != null,
      })
    }
    const order = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6']
    return order.filter((r) => map[r]?.length).map((r) => ({ round: r, label: ROUND_LABELS[r] || r, games: map[r] }))
  }, [games, teamName])

  const stats = useMemo(() => {
    let withResult = 0
    let correct = 0
    for (const g of games) {
      const winner = results[g.slot]
      if (winner == null) continue
      withResult++
      const pickId = (g.prob_team1 >= g.prob_team2) ? g.team1_id : g.team2_id
      if (Number(winner) === Number(pickId)) correct++
    }
    return { withResult, correct }
  }, [games, results])

  const setWinner = useCallback((slot, teamId) => {
    const next = { ...results, [slot]: teamId }
    setResults(next)
    saveResults(next)
    setEditingSlot(null)
  }, [results])

  const clearResult = useCallback((slot) => {
    const next = { ...results }
    delete next[slot]
    setResults(next)
    saveResults(next)
    setEditingSlot(null)
  }, [results])

  const clearAllResults = useCallback(() => {
    setResults({})
    saveResults({})
    setEditingSlot(null)
  }, [])

  if (byRound.length === 0) {
    return <p className="tab-empty">No games in bracket. Run simulation to see Adam&apos;s picks.</p>
  }

  return (
    <div className="adams-picks">
      <p className="tab-meta">
        Model picks for the whole tournament. Record actual winners as games finish to see how the picks did.
      </p>
      {stats.withResult > 0 && (
        <div className="adams-picks-stats">
          <strong>Record:</strong> {stats.correct} of {stats.withResult} correct
          {stats.withResult > 0 && (
            <span className="adams-picks-pct">
              ({((stats.correct / stats.withResult) * 100).toFixed(0)}%)
            </span>
          )}
          <button type="button" className="btn-clear-results" onClick={clearAllResults}>
            Clear all results
          </button>
        </div>
      )}
      {byRound.map(({ round, label, games: roundGames }) => (
        <section key={round} className="adams-picks-round">
          <h3>{label}</h3>
          <ul className="adams-picks-list">
            {roundGames.map((g) => {
              const actualWinner = results[g.slot] != null ? Number(results[g.slot]) : null
              const isCorrect = actualWinner != null && actualWinner === Number(g.pickId)
              const isWrong = actualWinner != null && actualWinner !== Number(g.pickId)
              const isEditing = editingSlot === g.slot
              return (
                <li key={g.slot} className={`adams-picks-row ${isCorrect ? 'correct' : ''} ${isWrong ? 'wrong' : ''}`}>
                  <span className="adams-picks-slot">{g.slot}</span>
                  <span className="adams-picks-matchup">
                    {g.team1}
                    {g.seed1 != null && <span className="seed">({g.seed1})</span>}
                    {' vs '}
                    {g.team2}
                    {g.seed2 != null && <span className="seed">({g.seed2})</span>}
                  </span>
                  {g.hasPick ? (
                    <>
                      <span className="adams-picks-pick">
                        Pick: {teamName(g.pickId)} ({(g.pickPct * 100).toFixed(0)}%)
                      </span>
                      {actualWinner == null ? (
                        isEditing ? (
                          <span className="adams-picks-set-winner">
                            Winner:
                            <button type="button" onClick={() => setWinner(g.slot, g.team1_id)}>{teamName(g.team1_id)}</button>
                            <button type="button" onClick={() => setWinner(g.slot, g.team2_id)}>{teamName(g.team2_id)}</button>
                            <button type="button" className="btn-cancel" onClick={() => setEditingSlot(null)}>Cancel</button>
                          </span>
                        ) : (
                          <button type="button" className="btn-set-result" onClick={() => setEditingSlot(g.slot)}>
                            Set result
                          </button>
                        )
                      ) : (
                        <span className="adams-picks-result">
                          {isCorrect && <span className="result-badge correct">✓ Correct</span>}
                          {isWrong && <span className="result-badge wrong">✗ Wrong</span>}
                          <span className="actual-winner">Actual: {teamName(actualWinner)}</span>
                          <button type="button" className="btn-clear-one" onClick={() => clearResult(g.slot)} title="Clear result">×</button>
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="tbd">TBD</span>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
