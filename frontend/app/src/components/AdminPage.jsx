/**
 * Admin bracket-filling page — pick winners game by game.
 * Each pick submits a result to the API and prunes all brackets that got it wrong.
 * Hidden from main nav — accessible via Ctrl+Shift+A.
 */

import { useState, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { submitResult, fetchBracket } from '../api/client'
import useTournamentStore from '../store/tournamentStore'

const REGIONS = ['South', 'East', 'West', 'Midwest']

const R64_PAIRS = [
  [1, 16], [8, 9], [5, 12], [4, 13],
  [6, 11], [3, 14], [7, 10], [2, 15],
]

const ROUND_NAMES = ['R64', 'R32', 'S16', 'E8']
const ROUND_LABELS = {
  R64: '1st Round',
  R32: '2nd Round',
  S16: 'Sweet 16',
  E8: 'Elite 8',
  F4: 'Final Four',
  Championship: 'Championship',
}

const REGION_ACCENT = {
  South: '#FF6B35',
  East: '#00D4FF',
  West: '#F59E0B',
  Midwest: '#22C55E',
}

/**
 * Build game tree structure for a region.
 * Returns a flat array of game slots: R64 (8 games) + R32 (4) + S16 (2) + E8 (1) = 15 games.
 * Each game has: { round, gameNum, teamA, teamB, winner, feederA, feederB }
 */
function buildRegionGames(teams) {
  const teamBySeed = {}
  for (const t of teams || []) {
    teamBySeed[t.seed] = t
  }

  const games = []

  // R64: 8 games, teams are known from bracket
  for (let i = 0; i < 8; i++) {
    const [seedA, seedB] = R64_PAIRS[i]
    games.push({
      id: i,
      round: 'R64',
      gameNum: i + 1,
      teamA: teamBySeed[seedA] || { seed: seedA, name: `Seed ${seedA}` },
      teamB: teamBySeed[seedB] || { seed: seedB, name: `Seed ${seedB}` },
      winner: null,
      feederA: null,
      feederB: null,
    })
  }

  // R32: 4 games, fed by pairs of R64 games
  for (let i = 0; i < 4; i++) {
    games.push({
      id: 8 + i,
      round: 'R32',
      gameNum: i + 1,
      teamA: null,
      teamB: null,
      winner: null,
      feederA: i * 2,
      feederB: i * 2 + 1,
    })
  }

  // S16: 2 games, fed by pairs of R32 games
  for (let i = 0; i < 2; i++) {
    games.push({
      id: 12 + i,
      round: 'S16',
      gameNum: i + 1,
      teamA: null,
      teamB: null,
      winner: null,
      feederA: 8 + i * 2,
      feederB: 8 + i * 2 + 1,
    })
  }

  // E8: 1 game, fed by the two S16 games
  games.push({
    id: 14,
    round: 'E8',
    gameNum: 1,
    teamA: null,
    teamB: null,
    winner: null,
    feederA: 12,
    feederB: 13,
  })

  return games
}

/**
 * Propagate winners forward through the bracket.
 * Returns a new games array (immutable).
 */
function propagateWinners(games) {
  const updated = games.map((g) => ({ ...g }))

  for (let i = 8; i < 15; i++) {
    const game = updated[i]
    const feederA = updated[game.feederA]
    const feederB = updated[game.feederB]
    const newTeamA = feederA?.winner || null
    const newTeamB = feederB?.winner || null

    updated[i] = {
      ...game,
      teamA: newTeamA,
      teamB: newTeamB,
      // Clear winner if either feeder team changed
      winner:
        game.winner &&
        newTeamA?.seed === game.teamA?.seed &&
        newTeamB?.seed === game.teamB?.seed
          ? game.winner
          : null,
    }
  }

  return updated
}

/* ── Clickable team row inside a matchup ── */
function PickableTeam({ team, isWinner, isPickable, onClick, accent }) {
  const canClick = isPickable && team

  return (
    <button
      onClick={canClick ? onClick : undefined}
      disabled={!canClick}
      className="w-full flex items-center px-2.5 py-2 transition-all duration-150"
      style={{
        background: isWinner
          ? `linear-gradient(90deg, ${accent}20, ${accent}08)`
          : 'var(--bg-card)',
        border: isWinner
          ? `1px solid ${accent}60`
          : '1px solid var(--border-subtle)',
        cursor: canClick ? 'pointer' : 'default',
        opacity: team ? 1 : 0.4,
      }}
      onMouseEnter={(e) => {
        if (canClick) {
          e.currentTarget.style.background = `${accent}15`
          e.currentTarget.style.borderColor = `${accent}40`
        }
      }}
      onMouseLeave={(e) => {
        if (canClick) {
          e.currentTarget.style.background = isWinner
            ? `linear-gradient(90deg, ${accent}20, ${accent}08)`
            : 'var(--bg-card)'
          e.currentTarget.style.borderColor = isWinner
            ? `${accent}60`
            : 'var(--border-subtle)'
        }
      }}
    >
      <span
        className="font-mono font-bold min-w-[20px] text-xs text-center"
        style={{ color: accent, opacity: 0.8 }}
      >
        {team?.seed || ''}
      </span>
      <span
        className="flex-1 px-1.5 text-left whitespace-nowrap overflow-hidden text-ellipsis font-semibold text-sm"
        style={{
          color: team
            ? isWinner
              ? accent
              : 'var(--text-primary)'
            : 'var(--text-muted)',
        }}
      >
        {team?.name || 'TBD'}
      </span>
      {isWinner && (
        <span className="text-xs" style={{ color: accent }}>
          W
        </span>
      )}
    </button>
  )
}

/* ── Single matchup: two teams, click to pick winner ── */
function PickableMatchup({ game, accent, onPick, isPending }) {
  const bothTeamsReady = game.teamA && game.teamB
  const isPickable = bothTeamsReady && !game.winner && !isPending

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        border: game.winner
          ? `1px solid ${accent}40`
          : '1px solid var(--border-subtle)',
        boxShadow: game.winner ? `0 0 12px ${accent}10` : 'none',
        opacity: isPending ? 0.6 : 1,
      }}
    >
      <PickableTeam
        team={game.teamA}
        isWinner={game.winner?.seed === game.teamA?.seed}
        isPickable={isPickable}
        onClick={() => onPick(game, game.teamA, game.teamB)}
        accent={accent}
      />
      <PickableTeam
        team={game.teamB}
        isWinner={game.winner?.seed === game.teamB?.seed}
        isPickable={isPickable}
        onClick={() => onPick(game, game.teamB, game.teamA)}
        accent={accent}
      />
    </div>
  )
}

/* ── Region bracket picker ── */
function RegionPicker({ region, teams, regionGames, onPick, pendingGame }) {
  const accent = REGION_ACCENT[region]
  const roundGroups = ROUND_NAMES.map((round) =>
    regionGames.filter((g) => g.round === round)
  )

  const regionChampion = regionGames[14]?.winner

  return (
    <div className="space-y-4">
      {/* Region header */}
      <div
        className="flex items-center gap-2 py-2 px-3 rounded-lg"
        style={{
          background: `linear-gradient(90deg, ${accent}15, transparent)`,
          borderLeft: `3px solid ${accent}`,
        }}
      >
        <span className="font-display text-lg tracking-wider" style={{ color: accent }}>
          {region.toUpperCase()}
        </span>
        {regionChampion && (
          <span className="font-mono text-xs ml-auto" style={{ color: accent }}>
            CHAMPION: ({regionChampion.seed}) {regionChampion.name}
          </span>
        )}
      </div>

      {/* Games by round */}
      {roundGroups.map((games, roundIdx) => (
        <div key={roundIdx}>
          <div
            className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2 px-1"
            style={{ color: 'var(--text-secondary)' }}
          >
            {ROUND_LABELS[ROUND_NAMES[roundIdx]]}
          </div>
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns:
                games.length >= 4
                  ? 'repeat(auto-fill, minmax(200px, 1fr))'
                  : games.length >= 2
                  ? 'repeat(2, 1fr)'
                  : '1fr',
            }}
          >
            {games.map((game) => (
              <PickableMatchup
                key={game.id}
                game={game}
                accent={accent}
                onPick={onPick}
                isPending={pendingGame === game.id}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Final Four picker ── */
function FinalFourPicker({ finalFourGames, onPick, pendingGame }) {
  return (
    <div className="space-y-4">
      <div
        className="flex items-center gap-2 py-2 px-3 rounded-lg"
        style={{
          background: 'linear-gradient(90deg, rgba(255,107,53,0.15), transparent)',
          borderLeft: '3px solid var(--orange)',
        }}
      >
        <span className="font-display text-lg tracking-wider" style={{ color: 'var(--orange)' }}>
          FINAL FOUR
        </span>
      </div>

      {/* Semifinals */}
      <div>
        <div
          className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2 px-1"
          style={{ color: 'var(--text-secondary)' }}
        >
          Semifinals
        </div>
        <div className="grid grid-cols-2 gap-2">
          {finalFourGames.slice(0, 2).map((game) => (
            <PickableMatchup
              key={game.id}
              game={game}
              accent="var(--orange)"
              onPick={onPick}
              isPending={pendingGame === game.id}
            />
          ))}
        </div>
      </div>

      {/* Championship */}
      <div>
        <div
          className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2 px-1"
          style={{ color: 'var(--gold, #FFD700)' }}
        >
          Championship
        </div>
        <div className="max-w-sm mx-auto">
          <PickableMatchup
            game={finalFourGames[2]}
            accent="#FFD700"
            onPick={onPick}
            isPending={pendingGame === finalFourGames[2].id}
          />
        </div>
        {finalFourGames[2].winner && (
          <div
            className="text-center mt-3 py-3 rounded-lg"
            style={{
              background: 'linear-gradient(90deg, transparent, rgba(255,215,0,0.1), transparent)',
              border: '1px solid rgba(255,215,0,0.3)',
            }}
          >
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] mb-1" style={{ color: 'var(--text-muted)' }}>
              National Champion
            </div>
            <div className="font-display text-xl tracking-wider" style={{ color: '#FFD700' }}>
              ({finalFourGames[2].winner.seed}) {finalFourGames[2].winner.name}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function AdminPage() {
  const { adminKey, setAdminKey } = useTournamentStore()
  const queryClient = useQueryClient()

  // Fetch bracket data for team names
  const { data: bracketData } = useQuery({
    queryKey: ['bracket'],
    queryFn: fetchBracket,
  })

  // Game state per region: { South: [...15 games], East: [...], ... }
  const [regionGamesMap, setRegionGamesMap] = useState({})
  // Final four games: [semi1, semi2, championship]
  const [finalFourGames, setFinalFourGames] = useState([
    { id: 'f4-0', round: 'F4', gameNum: 1, teamA: null, teamB: null, winner: null },
    { id: 'f4-1', round: 'F4', gameNum: 2, teamA: null, teamB: null, winner: null },
    { id: 'f4-2', round: 'Championship', gameNum: 1, teamA: null, teamB: null, winner: null },
  ])
  const [pendingGame, setPendingGame] = useState(null)
  const [statusMsg, setStatusMsg] = useState(null)
  const [activeRegion, setActiveRegion] = useState('South')

  // Initialize region games when bracket data loads
  const initializedRegions = useMemo(() => {
    if (!bracketData?.regions) return {}
    const result = {}
    for (const region of REGIONS) {
      if (!regionGamesMap[region]) {
        const teams = bracketData.regions[region] || []
        result[region] = propagateWinners(buildRegionGames(teams))
      } else {
        result[region] = regionGamesMap[region]
      }
    }
    return result
  }, [bracketData, regionGamesMap])

  // Use initialized regions or existing state
  const currentRegionGames = initializedRegions

  // Update final four teams when region champions change
  const currentFinalFour = useMemo(() => {
    const southChamp = currentRegionGames.South?.[14]?.winner || null
    const eastChamp = currentRegionGames.East?.[14]?.winner || null
    const westChamp = currentRegionGames.West?.[14]?.winner || null
    const midwestChamp = currentRegionGames.Midwest?.[14]?.winner || null

    const updated = finalFourGames.map((g) => ({ ...g }))

    // Semi 1: South vs East champions
    updated[0] = { ...updated[0], teamA: southChamp, teamB: eastChamp }
    // Semi 2: West vs Midwest champions
    updated[1] = { ...updated[1], teamA: westChamp, teamB: midwestChamp }
    // Championship: winners of semis
    updated[2] = {
      ...updated[2],
      teamA: updated[0].winner || null,
      teamB: updated[1].winner || null,
    }

    // Clear championship winner if semifinal teams changed
    if (
      updated[2].winner &&
      (updated[2].teamA?.seed !== finalFourGames[2].teamA?.seed ||
        updated[2].teamB?.seed !== finalFourGames[2].teamB?.seed)
    ) {
      updated[2] = { ...updated[2], winner: null }
    }

    return updated
  }, [currentRegionGames, finalFourGames])

  const mutation = useMutation({
    mutationFn: (data) => submitResult(data, adminKey),
    onSuccess: (result, variables) => {
      const eliminated = result.eliminated?.toLocaleString() || 0
      const remaining = result.alive_remaining?.toLocaleString() || 0
      setStatusMsg({
        type: 'success',
        text: `Result recorded. ${eliminated} brackets eliminated, ${remaining} remaining.`,
      })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['brackets'] })
      queryClient.invalidateQueries({ queryKey: ['bracket'] })
      setPendingGame(null)
    },
    onError: (err) => {
      setStatusMsg({ type: 'error', text: err.message })
      setPendingGame(null)
    },
  })

  const handleRegionPick = (region, game, winner, loser) => {
    if (!adminKey.trim()) {
      setStatusMsg({ type: 'error', text: 'Admin key required. Enter it above.' })
      return
    }

    // Update local bracket state (immutable)
    const updatedGames = currentRegionGames[region].map((g) =>
      g.id === game.id ? { ...g, winner } : g
    )
    const propagated = propagateWinners(updatedGames)

    setRegionGamesMap((prev) => ({ ...prev, [region]: propagated }))
    setPendingGame(game.id)
    setStatusMsg(null)

    // Submit to API
    mutation.mutate({
      region,
      round: game.round,
      game_number: game.gameNum,
      winner_seed: winner.seed,
      loser_seed: loser.seed,
    })
  }

  const handleFinalFourPick = (game, winner, loser) => {
    if (!adminKey.trim()) {
      setStatusMsg({ type: 'error', text: 'Admin key required. Enter it above.' })
      return
    }

    const updatedFF = currentFinalFour.map((g) =>
      g.id === game.id ? { ...g, winner } : g
    )

    // If picking a semifinal winner, propagate to championship
    if (game.round === 'F4') {
      const idx = game.id === 'f4-0' ? 0 : 1
      updatedFF[2] = {
        ...updatedFF[2],
        [idx === 0 ? 'teamA' : 'teamB']: winner,
      }
    }

    setFinalFourGames(updatedFF)
    setPendingGame(game.id)
    setStatusMsg(null)

    const region = game.round === 'Championship' ? 'Final' : 'F4'
    mutation.mutate({
      region,
      round: game.round,
      game_number: game.gameNum,
      winner_seed: winner.seed,
      loser_seed: loser.seed,
    })
  }

  // Count completed games
  const completedCount = REGIONS.reduce((sum, region) => {
    const games = currentRegionGames[region] || []
    return sum + games.filter((g) => g.winner).length
  }, 0) + currentFinalFour.filter((g) => g.winner).length

  const MOBILE_TABS = [...REGIONS, 'Final Four']

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="text-center">
        <h2 className="font-display text-3xl tracking-wider" style={{ color: 'var(--orange)' }}>
          BRACKET CONTROL
        </h2>
        <p className="text-xs font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          PICK WINNERS · PRUNE BRACKETS · {completedCount}/63 GAMES
        </p>
      </div>

      {/* Admin key */}
      <div className="glass rounded-xl p-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <label
            className="text-[10px] font-mono uppercase tracking-[0.2em] shrink-0"
            style={{ color: 'var(--text-muted)' }}
          >
            Admin Key
          </label>
          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="Enter admin key..."
            className="flex-1 rounded-lg px-3 py-2 text-sm outline-none transition-all duration-200 focus:ring-1"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              '--tw-ring-color': 'var(--orange)',
            }}
          />
        </div>
      </div>

      {/* Status message */}
      {statusMsg && (
        <div
          className="text-sm p-3 rounded-lg font-mono"
          style={{
            color: statusMsg.type === 'success' ? 'var(--green-alive)' : 'var(--red-dead)',
            background:
              statusMsg.type === 'success'
                ? 'rgba(34,197,94,0.08)'
                : 'rgba(239,68,68,0.08)',
            border: `1px solid ${
              statusMsg.type === 'success'
                ? 'rgba(34,197,94,0.2)'
                : 'rgba(239,68,68,0.2)'
            }`,
          }}
        >
          {statusMsg.text}
        </div>
      )}

      {/* Region tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {MOBILE_TABS.map((tab) => {
          const isActive = activeRegion === tab
          const accent = REGION_ACCENT[tab] || 'var(--orange)'
          const regionGames = currentRegionGames[tab] || []
          const completedInRegion =
            tab === 'Final Four'
              ? currentFinalFour.filter((g) => g.winner).length
              : regionGames.filter((g) => g.winner).length
          const totalInRegion = tab === 'Final Four' ? 3 : 15

          return (
            <button
              key={tab}
              onClick={() => setActiveRegion(tab)}
              className="px-3 py-2 rounded-lg font-mono text-xs font-semibold tracking-wider whitespace-nowrap transition-all duration-200"
              style={{
                color: isActive ? 'white' : accent,
                backgroundColor: isActive ? (typeof accent === 'string' && accent.startsWith('#') ? accent : 'var(--orange)') : 'transparent',
                border: `1px solid ${isActive ? (typeof accent === 'string' && accent.startsWith('#') ? accent : 'var(--orange)') : accent + '40'}`,
              }}
            >
              {tab.toUpperCase()}
              <span className="ml-1.5 opacity-70">
                {completedInRegion}/{totalInRegion}
              </span>
            </button>
          )
        })}
      </div>

      {/* Bracket picker */}
      <div className="glass rounded-xl p-4" style={{ border: '1px solid var(--border-subtle)' }}>
        {activeRegion === 'Final Four' ? (
          <FinalFourPicker
            finalFourGames={currentFinalFour}
            onPick={(game, winner, loser) => handleFinalFourPick(game, winner, loser)}
            pendingGame={pendingGame}
          />
        ) : (
          <RegionPicker
            region={activeRegion}
            teams={bracketData?.regions?.[activeRegion]}
            regionGames={currentRegionGames[activeRegion] || []}
            onPick={(game, winner, loser) => handleRegionPick(activeRegion, game, winner, loser)}
            pendingGame={pendingGame}
          />
        )}
      </div>

      {/* Instructions */}
      <div
        className="glass rounded-xl p-4 space-y-2"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <h4 className="font-display text-base tracking-wider" style={{ color: 'var(--cyan)' }}>
          HOW IT WORKS
        </h4>
        <div className="space-y-1.5 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>01</span>
            Click a team to pick them as the winner of that game.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>02</span>
            The result is sent to the API, which prunes all brackets that picked differently.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>03</span>
            Winners advance to the next round automatically.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>04</span>
            The survival graph updates in real-time as brackets are eliminated.
          </p>
        </div>
        <div className="pt-2 text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          Access this page: Ctrl+Shift+A
        </div>
      </div>
    </div>
  )
}
