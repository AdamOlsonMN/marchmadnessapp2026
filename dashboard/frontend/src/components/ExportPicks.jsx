/**
 * Export picks: copy summary to clipboard, print-friendly label.
 */
import { useCallback, useState } from 'react'

export default function ExportPicks({ games = [], teamName }) {
  const [copied, setCopied] = useState(false)

  const buildSummary = useCallback(() => {
    const lines = ['2026 model picks', '']
    for (const g of games) {
      const p1 = g.prob_team1 ?? 0
      const p2 = g.prob_team2 ?? 0
      const pick = p1 >= p2 ? g.team1_id : g.team2_id
      const pct = (p1 >= p2 ? p1 : p2) * 100
      const t1 = g.team1_id != null ? teamName(g.team1_id) : 'TBD'
      const t2 = g.team2_id != null ? teamName(g.team2_id) : 'TBD'
      lines.push(`${g.slot || '?'}: ${t1} vs ${t2} → ${teamName(pick)} (${pct.toFixed(0)}%)`)
    }
    return lines.join('\n')
  }, [games, teamName])

  const copySummary = useCallback(() => {
    const text = buildSummary()
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [buildSummary])

  if (!games.length) return null

  return (
    <div className="export-picks">
      <button type="button" className="btn-export" onClick={copySummary}>
        {copied ? 'Copied!' : 'Copy picks summary'}
      </button>
    </div>
  )
}
