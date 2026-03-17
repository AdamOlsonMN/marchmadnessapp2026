/**
 * 2026 model picks: matchup, model pick, confidence, and why (explanation).
 */
import { useMemo } from 'react'

const ROUND_LABELS = { R1: 'Round 1', R2: 'Round 2', R3: 'Sweet 16', R4: 'Elite 8', R5: 'Final Four', R6: 'Championship' }

export default function ModelPicks({ games = [], teams = [], teamName, pickSummary = null }) {
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
        team1: g.team1_id != null ? teamName(g.team1_id) : 'TBD',
        team2: g.team2_id != null ? teamName(g.team2_id) : 'TBD',
        seed1: g.seed1,
        seed2: g.seed2,
        pickId,
        pickPct,
        hasPick: g.team1_id != null && g.team2_id != null,
        explanation: g.explanation || null,
      })
    }
    const order = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6']
    return order.filter((r) => map[r]?.length).map((r) => ({ round: r, label: ROUND_LABELS[r] || r, games: map[r] }))
  }, [games, teamName])

  if (byRound.length === 0) {
    return <p className="tab-empty">No games in bracket. Run simulation to see model picks.</p>
  }

  return (
    <div className="model-picks">
      {pickSummary && (pickSummary.strongestPicks?.length > 0 || pickSummary.coinFlips?.length > 0) && (
        <section className="pick-summary-block">
          <h3>Summary</h3>
          <div className="pick-summary-grid">
            {pickSummary.strongestPicks?.length > 0 && (
              <div className="pick-summary-box">
                <h4>Strongest picks (≥70%)</h4>
                <ul>
                  {pickSummary.strongestPicks.slice(0, 8).map((gg) => {
                    const pick = gg.prob_team1 >= gg.prob_team2 ? gg.team1_id : gg.team2_id
                    const pct = Math.max(gg.prob_team1, gg.prob_team2) * 100
                    return (
                      <li key={gg.slot}>
                        {teamName(pick)} <span className="pct">{(pct).toFixed(0)}%</span>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}
            {pickSummary.coinFlips?.length > 0 && (
              <div className="pick-summary-box">
                <h4>Coin flips (45–55%)</h4>
                <ul>
                  {pickSummary.coinFlips.slice(0, 8).map((gg) => (
                    <li key={gg.slot}>
                      {teamName(gg.team1_id)} vs {teamName(gg.team2_id)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}
      {byRound.map(({ round, label, games: roundGames }) => (
        <section key={round} className="model-picks-round">
          <h3>{label}</h3>
          <ul className="data-list picks-list">
            {roundGames.map((g) => (
              <li key={g.slot}>
                <span className="matchup">
                  {g.team1}
                  {g.seed1 != null && <span className="seed">({g.seed1})</span>}
                  {' vs '}
                  {g.team2}
                  {g.seed2 != null && <span className="seed">({g.seed2})</span>}
                </span>
                {g.hasPick ? (
                  <>
                    <span className="pick">{g.pickId != null ? teamName(g.pickId) : '—'}</span>
                    <span className="pct">{(g.pickPct * 100).toFixed(1)}%</span>
                    {g.explanation?.summary && (
                      <span className="pick-why" title={g.explanation.summary}> — {g.explanation.summary}</span>
                    )}
                  </>
                ) : (
                  <span className="tbd">TBD</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
