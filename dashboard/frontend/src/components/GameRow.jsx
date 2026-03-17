export default function GameRow({ game, teamName, fixedWinner, onLock, onUnlock }) {
  if (!game) return null
  const p1 = game.prob_team1 ?? 0.5
  const p2 = game.prob_team2 ?? 0.5
  const locked = fixedWinner != null
  const lockTeam1 = fixedWinner === game.team1_id
  const lockTeam2 = fixedWinner === game.team2_id

  const handleTeamClick = (teamId) => {
    if (locked && fixedWinner === teamId) {
      onUnlock?.(game.slot)
    } else if (!locked) {
      onLock?.(game.slot, teamId)
    }
  }

  return (
    <div className={`game-row-card ${locked ? 'game-row-locked' : ''}`}>
      <div className="game-row-slot">{game.slot}</div>
      <div className="game-row-matchup">
        <button
          type="button"
          className={`game-row-team team1 ${lockTeam1 ? 'locked' : ''}`}
          style={{ '--prob': p1 }}
          onClick={() => handleTeamClick(game.team1_id)}
          aria-pressed={lockTeam1}
          aria-label={lockTeam1 ? `Unlock ${teamName(game.team1_id)} as winner` : `Pick ${teamName(game.team1_id)} to win`}
        >
          <span className="team-name">{teamName(game.team1_id)}</span>
          <span className="team-seed">({game.seed1})</span>
          <span className="team-prob">{Math.round(p1 * 100)}%</span>
          {lockTeam1 && (
            <span className="lock-icon" aria-hidden>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </span>
          )}
        </button>
        <div className="game-row-vs">vs</div>
        <button
          type="button"
          className={`game-row-team team2 ${lockTeam2 ? 'locked' : ''}`}
          style={{ '--prob': p2 }}
          onClick={() => handleTeamClick(game.team2_id)}
          aria-pressed={lockTeam2}
          aria-label={lockTeam2 ? `Unlock ${teamName(game.team2_id)} as winner` : `Pick ${teamName(game.team2_id)} to win`}
        >
          <span className="team-name">{teamName(game.team2_id)}</span>
          <span className="team-seed">({game.seed2})</span>
          <span className="team-prob">{Math.round(p2 * 100)}%</span>
          {lockTeam2 && (
            <span className="lock-icon" aria-hidden>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </span>
          )}
        </button>
      </div>
      <div className="game-row-bar">
        <div className="bar-fill team1" style={{ width: `${p1 * 100}%` }} />
        <div className="bar-fill team2" style={{ width: `${p2 * 100}%` }} />
      </div>
    </div>
  )
}
