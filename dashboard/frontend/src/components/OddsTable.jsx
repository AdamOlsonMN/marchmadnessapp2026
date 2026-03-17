/**
 * 538-style full odds table: all teams with Champion %, Final Four %, Elite 8 %, Sweet 16 %, R2 %.
 * Sortable by column.
 */
import { useMemo } from 'react'

const COLS = [
  { key: 'champ', label: 'Champ %', round: 'champ' },
  { key: 'final4', label: 'Final Four', round: 'final4' },
  { key: 'elite8', label: 'Elite 8', round: 'elite8' },
  { key: 'sweet16', label: 'Sweet 16', round: 'sweet16' },
  { key: 'r2', label: 'R2', round: 'r2' },
]

export default function OddsTable({ teams = [], championOdds = {}, advancement = {}, teamName, sort, onSort }) {
  const rows = useMemo(() => {
    const tidToChamp = championOdds || {}
    const adv = advancement || {}
    return teams.map((t, i) => ({
      rank: i + 1,
      id: t.id,
      name: t.name || teamName(t.id),
      seed: t.seed ?? '—',
      region: t.region ?? '—',
      champ: tidToChamp[String(t.id)] ?? 0,
      final4: adv.final4?.[String(t.id)] ?? 0,
      elite8: adv.elite8?.[String(t.id)] ?? 0,
      sweet16: adv.sweet16?.[String(t.id)] ?? 0,
      r2: adv.r2?.[String(t.id)] ?? 0,
    }))
  }, [teams, championOdds, advancement, teamName])

  const sortedRows = useMemo(() => {
    const { key, dir } = sort
    const mult = dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const va = a[key] ?? 0
      const vb = b[key] ?? 0
      return mult * (va - vb)
    })
  }, [rows, sort])

  const handleSort = (key) => {
    onSort((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'desc' ? 'asc' : 'desc',
    }))
  }

  return (
    <div className="odds-table-wrap">
      <table className="odds-table">
        <thead>
          <tr>
            <th className="col-rank">#</th>
            <th className="col-team">Team</th>
            <th className="col-seed">Seed</th>
            <th className="col-region">Region</th>
            {COLS.map(({ key, label }) => (
              <th key={key} className="col-pct">
                <button
                  type="button"
                  className={`th-sort ${sort.key === key ? `th-sort-${sort.dir}` : ''}`}
                  onClick={() => handleSort(key)}
                >
                  {label}
                  <span className="th-sort-icon" aria-hidden>{sort.key === key ? (sort.dir === 'desc' ? ' ↓' : ' ↑') : ' ⇅'}</span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((r, i) => (
            <tr key={r.id}>
              <td className="col-rank">{i + 1}</td>
              <td className="col-team">{r.name}</td>
              <td className="col-seed">{r.seed}</td>
              <td className="col-region">{r.region}</td>
              <td className="col-pct col-champ">{formatPct(r.champ)}</td>
              <td className="col-pct">{formatPct(r.final4)}</td>
              <td className="col-pct">{formatPct(r.elite8)}</td>
              <td className="col-pct">{formatPct(r.sweet16)}</td>
              <td className="col-pct">{formatPct(r.r2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatPct(p) {
  if (p == null || p === 0) return '—'
  const x = p * 100
  return x >= 0.1 ? `${x.toFixed(1)}%` : x >= 0.01 ? `${x.toFixed(2)}%` : '<0.01%'
}
