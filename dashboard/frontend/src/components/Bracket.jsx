import GameRow from './GameRow'

const REGIONS = ['W', 'X', 'Y', 'Z']

export default function Bracket({ games = [], teams = [], slotOrder = [], fixedWinners = {}, onLock, onUnlock }) {
  const teamsById = Object.fromEntries((teams || []).map((t) => [t.id, t]))
  const teamName = (id) => teamsById[id]?.name ?? `Team ${id}`

  const gamesBySlot = Object.fromEntries((games || []).map((g) => [g.slot, g]))

  const slotsByRegion = {}
  REGIONS.forEach((r) => (slotsByRegion[r] = []))
  for (const slot of slotOrder || []) {
    if (slot.startsWith('R1') && slot.length >= 4) {
      const region = slot.charAt(2)
      if (REGIONS.includes(region)) slotsByRegion[region].push(slot)
    }
  }

  return (
    <div className="bracket">
      <div className="bracket-regions">
        {REGIONS.map((region) => (
          <div key={region} className="bracket-region">
            <h3 className="region-title">Region {region}</h3>
            <div className="region-games">
              {(slotsByRegion[region] || []).map((slot) => {
                const game = gamesBySlot[slot]
                const fixedWinner = fixedWinners[slot] ?? null
                if (!game) {
                  return (
                    <div key={slot} className="game-row-card game-row-empty" data-slot={slot}>
                      —
                    </div>
                  )
                }
                return (
                  <GameRow
                    key={slot}
                    game={game}
                    teamName={teamName}
                    fixedWinner={fixedWinner}
                    onLock={onLock}
                    onUnlock={onUnlock}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
