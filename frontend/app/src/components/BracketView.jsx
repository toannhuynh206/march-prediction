/**
 * NCAA-style horizontal bracket view.
 * Shows all 4 regions with R64→E8 matchups plus Final Four center.
 */

import { useQuery } from '@tanstack/react-query'
import { fetchBracket } from '../api/client'

const ROUND_LABELS = ['R64', 'R32', 'S16', 'E8']
const ROUND_DISPLAY = { R64: 'Round of 64', R32: 'Round of 32', S16: 'Sweet 16', E8: 'Elite 8' }

// R64 seed pairings in bracket order
const R64_PAIRS = [
  [1, 16], [8, 9], [5, 12], [4, 13],
  [6, 11], [3, 14], [7, 10], [2, 15],
]

function TeamCell({ seed, name, isWinner, isLoser, isTbd, prob }) {
  let cls = 'flex items-center h-[26px] px-1.5 text-[11px] border border-gray-200 min-w-[148px] transition-colors'
  if (isWinner) cls += ' bg-green-50 border-green-300'
  else if (isLoser) cls += ' bg-red-50 border-red-200 opacity-50'
  else if (isTbd) cls += ' opacity-25 italic'
  else cls += ' bg-white hover:bg-gray-50'

  return (
    <div className={cls}>
      <span className="font-bold min-w-[17px] text-[10px] text-center opacity-60"
            style={{ color: 'var(--midnight)' }}>{seed}</span>
      <span className={`flex-1 px-1 whitespace-nowrap overflow-hidden text-ellipsis font-medium ${isWinner ? 'font-bold text-green-700' : ''} ${isLoser ? 'line-through text-gray-400' : ''}`}>
        {name || 'TBD'}
      </span>
      {prob != null && (
        <span className="text-[9px] font-semibold text-gray-400 min-w-[30px] text-right">
          {(prob * 100).toFixed(0)}%
        </span>
      )}
    </div>
  )
}

function Matchup({ teamA, teamB, probA, upset, spacing }) {
  const margins = { R64: 'my-[1px]', R32: 'my-[15px]', S16: 'my-[43px]', E8: 'my-[99px]' }
  return (
    <div className={`relative ${margins[spacing] || 'my-[1px]'}`}>
      <TeamCell seed={teamA?.seed} name={teamA?.name} prob={probA} />
      <TeamCell seed={teamB?.seed} name={teamB?.name} prob={probA != null ? 1 - probA : null} />
      {upset && (
        <div className="absolute -right-2 top-1/2 -translate-y-1/2 w-[15px] h-[15px] rounded-full flex items-center justify-center text-[7px] font-extrabold text-white z-10"
             style={{ background: 'linear-gradient(135deg, var(--orange), #D4510F)' }}>!</div>
      )}
    </div>
  )
}

function RegionBracket({ region, teams, matchups, rtl }) {
  // Build team lookup by seed
  const teamBySeed = {}
  for (const t of teams || []) {
    teamBySeed[t.seed] = t
  }

  // Build matchup lookup by game_index
  const matchupByGame = {}
  for (const m of matchups || []) {
    if (m.region === region) {
      matchupByGame[m.game_index] = m
    }
  }

  // R64 matchups
  const r64Games = R64_PAIRS.map((pair, i) => {
    const m = matchupByGame[i + 1] || {}  // game_index is 1-based in DB
    return {
      teamA: teamBySeed[pair[0]],
      teamB: teamBySeed[pair[1]],
      probA: m.p_final,
    }
  })

  const roundCols = (
    <div className={`flex ${rtl ? 'flex-row-reverse' : ''}`}>
      {/* R64 */}
      <div className="flex flex-col justify-center min-w-[155px]">
        <div className="text-[8px] font-semibold uppercase text-gray-400 tracking-wider text-center mb-1">
          Round 1
        </div>
        {r64Games.map((g, i) => (
          <Matchup key={i} teamA={g.teamA} teamB={g.teamB} probA={g.probA} spacing="R64" />
        ))}
      </div>
      {/* R32-E8 placeholder columns */}
      {['R32', 'S16', 'E8'].map((rd) => (
        <div key={rd} className="flex flex-col justify-center min-w-[155px]">
          <div className="text-[8px] font-semibold uppercase text-gray-400 tracking-wider text-center mb-1">
            {ROUND_DISPLAY[rd]}
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="mb-4">
      <div className="text-[13px] font-bold uppercase tracking-wider py-1.5 px-2.5 mb-1.5 rounded-r flex justify-between items-center"
           style={{ color: 'var(--midnight)', background: 'linear-gradient(90deg, rgba(30,58,95,0.06), transparent)', borderLeft: '3px solid var(--orange)' }}>
        {region}
      </div>
      {roundCols}
    </div>
  )
}

export default function BracketView() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['bracket'],
    queryFn: fetchBracket,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        Loading bracket...
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Error loading bracket: {error.message}
      </div>
    )
  }

  const { regions, matchups } = data
  const regionNames = ['South', 'East', 'West', 'Midwest']

  return (
    <div className="overflow-x-auto bg-white rounded-lg shadow-sm p-4">
      <div className="grid grid-cols-[1fr_auto_1fr] min-w-[1500px] items-start">
        {/* Left side: South + East */}
        <div className="flex flex-col gap-4">
          <RegionBracket region="South" teams={regions.South} matchups={matchups} />
          <RegionBracket region="East" teams={regions.East} matchups={matchups} />
        </div>

        {/* Center: Final Four */}
        <div className="flex flex-col items-center justify-center min-h-[800px] px-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-4"
               style={{ color: 'var(--orange)' }}>Final Four</div>
          <div className="w-[180px] rounded-xl p-4 space-y-3"
               style={{ background: 'linear-gradient(180deg, #FFF8F0 0%, #FFF0E0 100%)', border: '2px solid var(--gold)' }}>
            <div className="text-[10px] font-semibold text-center uppercase tracking-wider text-gray-400">Championship</div>
            <div className="h-[52px] border-2 border-dashed border-gray-200 rounded-lg flex items-center justify-center text-[11px] text-gray-300 italic">
              TBD
            </div>
          </div>
        </div>

        {/* Right side: West + Midwest (RTL) */}
        <div className="flex flex-col gap-4">
          <RegionBracket region="West" teams={regions.West} matchups={matchups} rtl />
          <RegionBracket region="Midwest" teams={regions.Midwest} matchups={matchups} rtl />
        </div>
      </div>
    </div>
  )
}
