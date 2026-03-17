/**
 * ESPN-style bracket: round columns (1st Round → Championship), TBD slots for later rounds,
 * connector lines. R1 games are interactive; R2+ show "Winner of X" or resolved team when locked.
 */
import { useMemo } from 'react'
import GameRow from './GameRow'

const ROUND_LABELS = {
  R1: '1st Round',
  R2: '2nd Round',
  R3: 'Sweet 16',
  R4: 'Elite 8',
  R5: 'Final Four',
  R6: 'Championship',
}

export default function BracketESPN({ games = [], teams = [], slotOrder = [], slotTree = {}, fixedWinners = {}, nextGameProbs = null, onLock, onUnlock }) {
  const teamsById = useMemo(() => Object.fromEntries((teams || []).map((t) => [t.id, t])), [teams])
  const teamName = (id) => teamsById[id]?.name ?? `Team ${id}`

  const gamesBySlot = useMemo(() => Object.fromEntries((games || []).map((g) => [g.slot, g])), [games])

  // Build round columns: R1 display order (pairs that feed R2), then R2, R3, R4, R5, R6
  const { r1DisplayOrder, rounds } = useMemo(() => {
    const order = slotOrder || []
    const tree = slotTree || {}
    const r2Slots = order.filter((s) => s.startsWith('R2'))
    const r1Order = r2Slots.flatMap((r2) => tree[r2] || [])
    const rounds = {}
    for (const slot of order) {
      const round = slot.slice(0, 2) // R1, R2, ...
      if (!rounds[round]) rounds[round] = []
      rounds[round].push(slot)
    }
    return { r1DisplayOrder: r1Order, rounds }
  }, [slotOrder, slotTree])

  // Resolve winner for a slot (from fixedWinners or null)
  const getWinner = (slot) => fixedWinners[slot] ?? null

  const rowHeight = 36
  const totalRows = 32

  return (
    <div className="bracket-espn">
      <div className="bracket-espn-rounds">
        {['R1', 'R2', 'R3', 'R4', 'R5', 'R6'].map((roundKey) => {
          const slots = rounds[roundKey]
          if (!slots || slots.length === 0) return null
          const span = totalRows / slots.length
          const label = ROUND_LABELS[roundKey] || roundKey
          return (
            <div key={roundKey} className="bracket-espn-column" style={{ '--rows': slots.length, '--span': span }}>
              <div className="bracket-espn-round-label">{label}</div>
              <div className="bracket-espn-cells">
                {(roundKey === 'R1' ? r1DisplayOrder : slots).map((slot, idx) => {
                  const game = gamesBySlot[slot]
                  const fixedWinner = getWinner(slot)
                  const rowStart = roundKey === 'R1' ? idx + 1 : idx * span + 1
                  const rowSpan = roundKey === 'R1' ? 1 : Math.round(span)

                  if (roundKey === 'R1' && game) {
                    return (
                      <div
                        key={slot}
                        className="bracket-espn-cell bracket-espn-cell-r1"
                        style={{ gridRow: `${rowStart} / span ${rowSpan}` }}
                      >
                        <GameRow
                          game={game}
                          teamName={teamName}
                          fixedWinner={fixedWinner}
                          onLock={onLock}
                          onUnlock={onUnlock}
                        />
                      </div>
                    )
                  }

                  if (roundKey !== 'R1') {
                    const inputs = slotTree[slot]
                    const in1 = Array.isArray(inputs) ? inputs[0] : inputs?.[0]
                    const in2 = Array.isArray(inputs) ? inputs[1] : inputs?.[1]
                    const winner1 = in1 ? getWinner(in1) : null
                    const winner2 = in2 ? getWinner(in2) : null
                    const bothLocked = winner1 != null && winner2 != null
                    const oneLocked = winner1 != null || winner2 != null
                    // When neither side is set, show "TBD" so we don't label opponent as "Winner of X" yet.
                    // When one is locked, show that team and "Winner of R1W8" so it's clear which game we're waiting on.
                    const side1 = winner1 != null ? teamName(winner1) : oneLocked && in1 ? `Winner of ${in1}` : 'TBD'
                    const side2 = winner2 != null ? teamName(winner2) : oneLocked && in2 ? `Winner of ${in2}` : 'TBD'
                    const nextProbs = nextGameProbs?.[slot]
                    return (
                      <div
                        key={slot}
                        className={`bracket-espn-cell bracket-espn-cell-tbd ${bothLocked ? 'has-winners' : ''}`}
                        style={{ gridRow: `${rowStart} / span ${rowSpan}` }}
                      >
                        <div className="bracket-espn-cell-slot">{slot}</div>
                        <div className="bracket-espn-cell-teams">
                          <div className="bracket-espn-team">
                            {side1}
                            {nextProbs && winner1 != null && nextProbs[String(winner1)] != null && (
                              <span className="bracket-espn-next-pct"> {(nextProbs[String(winner1)] * 100).toFixed(0)}%</span>
                            )}
                          </div>
                          <div className="bracket-espn-vs">vs</div>
                          <div className="bracket-espn-team">
                            {side2}
                            {nextProbs && winner2 != null && nextProbs[String(winner2)] != null && (
                              <span className="bracket-espn-next-pct"> {(nextProbs[String(winner2)] * 100).toFixed(0)}%</span>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  }

                  return (
                    <div
                      key={slot}
                      className="bracket-espn-cell bracket-espn-cell-empty"
                      style={{ gridRow: `${rowStart} / span ${rowSpan}` }}
                    >
                      <span className="bracket-espn-cell-slot">{slot}</span>
                      <span>TBD</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      <BracketConnectors />
    </div>
  )
}

function BracketConnectors() {
  return null
}
