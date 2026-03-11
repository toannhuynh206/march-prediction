/**
 * NCAA-style bracket view — proper converging tournament tree.
 * Left regions (South/East) flow left→right, right regions (West/Midwest) flow right→left.
 * Semifinals connect from each side's Elite 8, converging to Championship in the center.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBracket } from '../api/client'

const R64_PAIRS = [
  [1, 16], [8, 9], [5, 12], [4, 13],
  [6, 11], [3, 14], [7, 10], [2, 15],
]

const ROUND_NAMES = ['1st Round', '2nd Round', 'Sweet 16', 'Elite 8']

const REGION_ACCENT = {
  South: '#FF6B35',
  East: '#00D4FF',
  West: '#F59E0B',
  Midwest: '#22C55E',
}

const CELL_W = 98
const CELL_H = 22
const CONN_W = 8

/* ── Team line inside a matchup cell ── */
function TeamLine({ seed, name, prob, isTop, accent }) {
  return (
    <div
      className="flex items-center px-1.5"
      style={{
        height: CELL_H,
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderBottomWidth: isTop ? '0' : '1px',
        borderTopWidth: isTop ? '1px' : '0',
      }}
    >
      <span className="font-mono font-bold min-w-[16px] text-[10px] text-center" style={{ color: accent || 'var(--orange)', opacity: 0.8 }}>
        {seed || ''}
      </span>
      <span
        className="flex-1 px-1 whitespace-nowrap overflow-hidden text-ellipsis font-semibold text-[11px]"
        style={{ color: name ? 'var(--text-primary)' : 'var(--text-muted)' }}
      >
        {name || 'TBD'}
      </span>
      {prob != null && (
        <span className="font-mono text-[9px]" style={{ color: 'var(--text-muted)' }}>
          {(prob * 100).toFixed(0)}%
        </span>
      )}
    </div>
  )
}

/* ── Matchup cell: two teams stacked ── */
function MatchupCell({ teamA, teamB, probA, width }) {
  const w = width || CELL_W
  return (
    <div className="flex flex-col" style={{ width: w }}>
      <TeamLine seed={teamA?.seed} name={teamA?.name} prob={probA} isTop />
      <TeamLine
        seed={teamB?.seed}
        name={teamB?.name}
        prob={probA != null ? 1 - probA : null}
      />
    </div>
  )
}

/* ── TBD matchup placeholder ── */
function TbdMatchup({ width, label }) {
  const w = width || CELL_W
  return (
    <div className="flex flex-col" style={{ width: w }}>
      <div
        className="flex items-center px-1.5 text-[11px] italic"
        style={{
          height: CELL_H,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderBottom: '0',
          color: 'var(--text-muted)',
          opacity: 0.5,
        }}
      >
        {label || 'TBD'}
      </div>
      <div
        className="flex items-center px-1.5 text-[11px] italic"
        style={{
          height: CELL_H,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-muted)',
          opacity: 0.5,
        }}
      >
        TBD
      </div>
    </div>
  )
}

/* ── Bracket connector lines between rounds ── */
function ConnectorLines({ count, rtl }) {
  const connectors = []
  for (let i = 0; i < count; i++) {
    connectors.push(
      <div key={i} className="flex-1 flex items-center">
        <svg width={CONN_W} height="100%" viewBox={`0 0 ${CONN_W} 100`} preserveAspectRatio="none" className="h-full">
          {rtl ? (
            <>
              <line x1={CONN_W} y1="25" x2={CONN_W / 2} y2="25" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1={CONN_W} y1="75" x2={CONN_W / 2} y2="75" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1={CONN_W / 2} y1="25" x2={CONN_W / 2} y2="75" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1={CONN_W / 2} y1="50" x2="0" y2="50" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
            </>
          ) : (
            <>
              <line x1="0" y1="25" x2={CONN_W / 2} y2="25" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1="0" y1="75" x2={CONN_W / 2} y2="75" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1={CONN_W / 2} y1="25" x2={CONN_W / 2} y2="75" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1={CONN_W / 2} y1="50" x2={CONN_W} y2="50" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
            </>
          )}
        </svg>
      </div>
    )
  }
  return (
    <div className="flex flex-col" style={{ width: CONN_W, height: '100%' }}>
      {connectors}
    </div>
  )
}

/* ── Simple horizontal connector line ── */
function HorizConnector({ rtl }) {
  return (
    <div className="flex items-center" style={{ width: CONN_W }}>
      <svg width={CONN_W} height={CELL_H * 2} viewBox={`0 0 ${CONN_W} ${CELL_H * 2}`}>
        <line
          x1="0" y1={CELL_H} x2={CONN_W} y2={CELL_H}
          stroke="rgba(255,255,255,0.15)" strokeWidth="1"
        />
      </svg>
    </div>
  )
}

/* ── Single region bracket: 4 rounds converging ── */
function RegionBracket({ region, teams, matchups, rtl }) {
  const accent = REGION_ACCENT[region] || 'var(--orange)'

  const teamBySeed = {}
  for (const t of teams || []) {
    teamBySeed[t.seed] = t
  }

  const matchupByGame = {}
  for (const m of matchups || []) {
    if (m.region === region) {
      matchupByGame[m.game_index] = m
    }
  }

  const r64 = R64_PAIRS.map((pair, i) => {
    const m = matchupByGame[i + 1] || {}
    return {
      teamA: teamBySeed[pair[0]],
      teamB: teamBySeed[pair[1]],
      probA: m.p_final,
    }
  })

  const roundCounts = [8, 4, 2, 1]

  // Gaps so each later-round matchup centers between its two feeders
  // Matchup = 2 × CELL_H = 44px. R64 gap = 1px.
  // R32 gap = 44 + 2*1 = 46, S16 = 2*(44+46)-44 = 136, E8 = 2*(44+136)-44 = 316
  const gaps = [1, 46, 136, 316]

  const buildRoundColumn = (roundIdx, count) => {
    const gap = gaps[roundIdx]
    const items = []
    for (let i = 0; i < count; i++) {
      if (roundIdx === 0) {
        items.push(
          <MatchupCell
            key={i}
            teamA={r64[i].teamA}
            teamB={r64[i].teamB}
            probA={r64[i].probA}
          />
        )
      } else {
        items.push(<TbdMatchup key={i} />)
      }
    }
    return (
      <div className="flex flex-col items-center" style={{ gap: `${gap}px` }}>
        {items}
      </div>
    )
  }

  const connectorCounts = [4, 2, 1]
  const columns = []
  const order = rtl ? [3, 2, 1, 0] : [0, 1, 2, 3]

  for (let idx = 0; idx < order.length; idx++) {
    const roundIdx = order[idx]
    columns.push(
      <div key={`round-${roundIdx}`} className="flex flex-col">
        <div
          className="text-[10px] font-mono uppercase tracking-widest text-center mb-1 py-0.5"
          style={{ color: 'var(--text-secondary)' }}
        >
          {ROUND_NAMES[roundIdx]}
        </div>
        {buildRoundColumn(roundIdx, roundCounts[roundIdx])}
      </div>
    )

    if (idx < 3) {
      const cIdx = rtl ? (2 - idx) : idx
      columns.push(
        <div key={`conn-${idx}`} className="flex flex-col pt-5">
          <ConnectorLines count={connectorCounts[cIdx]} rtl={rtl} />
        </div>
      )
    }
  }

  return (
    <div className="animate-fade-up">
      {/* Region header */}
      <div
        className="flex items-center gap-2 py-1.5 px-3 mb-2 rounded-lg"
        style={{
          background: `linear-gradient(${rtl ? '270deg' : '90deg'}, ${accent}15, transparent)`,
          borderLeft: rtl ? 'none' : `3px solid ${accent}`,
          borderRight: rtl ? `3px solid ${accent}` : 'none',
          justifyContent: rtl ? 'flex-end' : 'flex-start',
        }}
      >
        <span className="font-display text-base tracking-wider" style={{ color: accent }}>
          {region.toUpperCase()}
        </span>
        <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>
          REGION
        </span>
      </div>

      <div className="flex items-center gap-0" style={{ justifyContent: rtl ? 'flex-end' : 'flex-start' }}>
        {columns}
      </div>
    </div>
  )
}

/* ── Loading skeleton ── */
function LoadingSkeleton() {
  return (
    <div className="glass rounded-xl p-8">
      <div className="flex flex-col items-center gap-4 py-16">
        <div
          className="w-12 h-12 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--orange)', borderTopColor: 'transparent' }}
        />
        <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
          LOADING BRACKET DATA...
        </span>
      </div>
    </div>
  )
}

/* ── Mobile: single matchup row ── */
function MobileMatchupRow({ teamA, teamB, probA, accent }) {
  return (
    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
      <div
        className="flex items-center px-3 py-2.5"
        style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border-subtle)' }}
      >
        <span className="font-mono font-bold w-7 text-xs text-center" style={{ color: accent, opacity: 0.8 }}>
          {teamA?.seed || ''}
        </span>
        <span className="flex-1 font-semibold text-sm" style={{ color: teamA?.name ? 'var(--text-primary)' : 'var(--text-muted)' }}>
          {teamA?.name || 'TBD'}
        </span>
        {probA != null && (
          <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
            {(probA * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div className="flex items-center px-3 py-2.5" style={{ background: 'var(--bg-card)' }}>
        <span className="font-mono font-bold w-7 text-xs text-center" style={{ color: accent, opacity: 0.8 }}>
          {teamB?.seed || ''}
        </span>
        <span className="flex-1 font-semibold text-sm" style={{ color: teamB?.name ? 'var(--text-primary)' : 'var(--text-muted)' }}>
          {teamB?.name || 'TBD'}
        </span>
        {probA != null && (
          <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
            {((1 - probA) * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  )
}

/* ── Mobile: single region view with rounds ── */
function MobileRegionView({ region, teams, matchups }) {
  const accent = REGION_ACCENT[region] || 'var(--orange)'

  const teamBySeed = {}
  for (const t of teams || []) {
    teamBySeed[t.seed] = t
  }

  const matchupByGame = {}
  for (const m of matchups || []) {
    if (m.region === region) {
      matchupByGame[m.game_index] = m
    }
  }

  const r64 = R64_PAIRS.map((pair, i) => {
    const m = matchupByGame[i + 1] || {}
    return {
      teamA: teamBySeed[pair[0]],
      teamB: teamBySeed[pair[1]],
      probA: m.p_final,
    }
  })

  const roundCounts = [8, 4, 2, 1]

  return (
    <div className="space-y-5 animate-fade-up">
      {ROUND_NAMES.map((roundName, roundIdx) => (
        <div key={roundIdx}>
          <div
            className="text-xs font-mono uppercase tracking-widest mb-2 px-1"
            style={{ color: 'var(--text-secondary)' }}
          >
            {roundName}
          </div>
          <div className="space-y-2">
            {Array.from({ length: roundCounts[roundIdx] }).map((_, i) => {
              if (roundIdx === 0) {
                return (
                  <MobileMatchupRow
                    key={i}
                    teamA={r64[i].teamA}
                    teamB={r64[i].teamB}
                    probA={r64[i].probA}
                    accent={accent}
                  />
                )
              }
              return (
                <MobileMatchupRow key={i} accent={accent} />
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Mobile: Final Four section ── */
function MobileFinalFour() {
  return (
    <div className="space-y-4 animate-fade-up">
      <div className="text-center">
        <div className="font-display text-xl tracking-[0.15em] mb-1" style={{ color: 'var(--orange)' }}>
          FINAL FOUR
        </div>
      </div>

      <div>
        <div className="text-xs font-mono uppercase tracking-widest mb-2 px-1" style={{ color: 'var(--text-secondary)' }}>
          Semifinals
        </div>
        <div className="space-y-2">
          <MobileMatchupRow accent="var(--orange)" />
          <MobileMatchupRow accent="var(--orange)" />
        </div>
      </div>

      <div>
        <div className="text-xs font-mono uppercase tracking-widest mb-2 px-1" style={{ color: 'var(--gold)' }}>
          Championship
        </div>
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: '1px solid var(--border-accent)', boxShadow: '0 0 30px rgba(255, 107, 53, 0.08)' }}
        >
          <div
            className="flex items-center px-3 py-3 text-sm italic font-mono"
            style={{ background: 'linear-gradient(90deg, rgba(255,107,53,0.06), var(--bg-card))', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}
          >
            TBD
          </div>
          <div
            className="flex items-center px-3 py-3 text-sm italic font-mono"
            style={{ background: 'linear-gradient(90deg, var(--bg-card), rgba(255,107,53,0.06))', color: 'var(--text-muted)' }}
          >
            TBD
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Mobile bracket with region tabs ── */
function MobileBracketView({ regions, matchups }) {
  const MOBILE_TABS = ['South', 'East', 'West', 'Midwest', 'Final Four']
  const [activeRegion, setActiveRegion] = useState('South')

  return (
    <div className="glass rounded-xl p-3">
      {/* Title */}
      <div className="text-center mb-3">
        <div className="font-display text-base tracking-wider" style={{ color: 'var(--text-primary)' }}>
          2025 NCAA TOURNAMENT BRACKET
        </div>
        <div className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
          64 TEAMS · 63 GAMES · 6 ROUNDS
        </div>
      </div>

      {/* Region tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-1">
        {MOBILE_TABS.map((tab) => {
          const isActive = activeRegion === tab
          const accent = REGION_ACCENT[tab] || 'var(--orange)'
          return (
            <button
              key={tab}
              onClick={() => setActiveRegion(tab)}
              className="px-3 py-1.5 rounded-lg font-mono text-[11px] font-semibold tracking-wider whitespace-nowrap transition-all duration-200"
              style={{
                color: isActive ? 'white' : accent,
                backgroundColor: isActive ? accent : 'transparent',
                border: `1px solid ${isActive ? accent : accent + '40'}`,
                boxShadow: isActive ? `0 0 15px ${accent}20` : 'none',
              }}
            >
              {tab.toUpperCase()}
            </button>
          )
        })}
      </div>

      {/* Region content */}
      {activeRegion === 'Final Four' ? (
        <MobileFinalFour />
      ) : (
        <MobileRegionView
          region={activeRegion}
          teams={regions?.[activeRegion]}
          matchups={matchups}
        />
      )}
    </div>
  )
}

/* ── Main bracket view ── */
export default function BracketView() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['bracket'],
    queryFn: fetchBracket,
  })

  if (isLoading) return <LoadingSkeleton />

  if (error) {
    return (
      <div className="glass rounded-xl p-6 glow-orange">
        <div className="flex items-center gap-3">
          <span className="text-2xl">!</span>
          <div>
            <p className="font-semibold" style={{ color: 'var(--orange)' }}>Error loading bracket</p>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{error.message}</p>
          </div>
        </div>
      </div>
    )
  }

  const { regions, matchups } = data

  return (
    <>
      {/* ═══ Mobile view: region tabs ═══ */}
      <div className="block lg:hidden">
        <MobileBracketView regions={regions} matchups={matchups} />
      </div>

      {/* ═══ Desktop view: full bracket tree ═══ */}
      <div className="hidden lg:block glass rounded-xl p-4">
        {/* Title bar */}
        <div className="flex items-center justify-between mb-3 px-2">
          <div className="font-display text-lg tracking-wider" style={{ color: 'var(--text-primary)' }}>
            2025 NCAA TOURNAMENT BRACKET
          </div>
          <div className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
            64 TEAMS · 63 GAMES · 6 ROUNDS
          </div>
        </div>

        <div className="flex items-stretch">
          {/* ═══ Left side: South (top) + East (bottom) ═══ */}
          <div className="flex-1 flex flex-col gap-5">
            <RegionBracket region="South" teams={regions?.South} matchups={matchups} />
            <RegionBracket region="East" teams={regions?.East} matchups={matchups} />
          </div>

          {/* ═══ Left SF connector ═══ */}
          <div className="flex flex-col pt-5">
            <ConnectorLines count={1} rtl={false} />
          </div>

          {/* ═══ Left Semifinal ═══ */}
          <div className="flex flex-col justify-center">
            <div>
              <div
                className="text-[10px] font-mono uppercase tracking-widest text-center mb-1 py-0.5"
                style={{ color: 'var(--text-secondary)' }}
              >
                Semifinal
              </div>
              <TbdMatchup width={CELL_W} />
            </div>
          </div>

          {/* ═══ Left SF → Championship connector ═══ */}
          <div className="flex flex-col justify-center">
            <HorizConnector />
          </div>

          {/* ═══ Championship (center) ═══ */}
          <div className="flex flex-col items-center justify-center shrink-0 px-1">
            <div
              className="font-display text-lg tracking-[0.15em] mb-3"
              style={{ color: 'var(--orange)' }}
            >
              FINAL FOUR
            </div>
            <div>
              <div
                className="text-[10px] font-mono font-semibold uppercase tracking-[0.12em] text-center mb-1 py-0.5"
                style={{ color: 'var(--gold)' }}
              >
                Championship
              </div>
              <div
                className="flex flex-col rounded-lg overflow-hidden"
                style={{
                  width: CELL_W,
                  boxShadow: '0 0 30px rgba(255, 107, 53, 0.08)',
                  border: '1px solid var(--border-accent)',
                }}
              >
                <div
                  className="flex items-center px-1.5 text-[11px] italic font-mono"
                  style={{
                    height: CELL_H,
                    background: 'linear-gradient(90deg, rgba(255,107,53,0.06), var(--bg-card))',
                    borderBottom: '1px solid var(--border-subtle)',
                    color: 'var(--text-muted)',
                  }}
                >
                  TBD
                </div>
                <div
                  className="flex items-center px-1.5 text-[11px] italic font-mono"
                  style={{
                    height: CELL_H,
                    background: 'linear-gradient(90deg, var(--bg-card), rgba(255,107,53,0.06))',
                    color: 'var(--text-muted)',
                  }}
                >
                  TBD
                </div>
              </div>
            </div>
          </div>

          {/* ═══ Championship → Right SF connector ═══ */}
          <div className="flex flex-col justify-center">
            <HorizConnector rtl />
          </div>

          {/* ═══ Right Semifinal ═══ */}
          <div className="flex flex-col justify-center">
            <div>
              <div
                className="text-[10px] font-mono uppercase tracking-widest text-center mb-1 py-0.5"
                style={{ color: 'var(--text-secondary)' }}
              >
                Semifinal
              </div>
              <TbdMatchup width={CELL_W} />
            </div>
          </div>

          {/* ═══ Right SF connector ═══ */}
          <div className="flex flex-col pt-5">
            <ConnectorLines count={1} rtl={true} />
          </div>

          {/* ═══ Right side: West (top) + Midwest (bottom) — RTL ═══ */}
          <div className="flex-1 flex flex-col gap-5">
            <RegionBracket region="West" teams={regions?.West} matchups={matchups} rtl />
            <RegionBracket region="Midwest" teams={regions?.Midwest} matchups={matchups} rtl />
          </div>
        </div>
      </div>
    </>
  )
}
