/**
 * Admin bracket-filling page — pick winners game by game.
 * Each pick submits a result to the API and prunes all brackets that got it wrong.
 * Hidden from main nav — accessible via Ctrl+Shift+A.
 */

import { useState, useMemo, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { submitResult, fetchBracket, fetchResults } from '../api/client'
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

// Map (round, game_number) → absolute game.id within region
const ROUND_OFFSET = { R64: 0, R32: 8, S16: 12, E8: 14 }

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
function PickableTeam({ team, isWinner, isLoser, isPendingPick, isPickable, onClick, accent }) {
  const canClick = isPickable && team

  return (
    <button
      onClick={canClick ? onClick : undefined}
      disabled={!canClick}
      className="w-full flex items-center px-2.5 py-2 transition-all duration-150"
      style={{
        background: isPendingPick
          ? `${accent}25`
          : isWinner
          ? `linear-gradient(90deg, ${accent}20, ${accent}08)`
          : 'var(--bg-card)',
        border: isPendingPick
          ? `2px dashed ${accent}`
          : isWinner
          ? `1px solid ${accent}60`
          : '1px solid var(--border-subtle)',
        cursor: canClick ? 'pointer' : 'default',
        opacity: isLoser ? 0.35 : team ? 1 : 0.4,
      }}
      onMouseEnter={(e) => {
        if (canClick) {
          e.currentTarget.style.background = `${accent}15`
          e.currentTarget.style.borderColor = accent
        }
      }}
      onMouseLeave={(e) => {
        if (canClick) {
          e.currentTarget.style.background = isPendingPick
            ? `${accent}25`
            : isWinner
            ? `linear-gradient(90deg, ${accent}20, ${accent}08)`
            : 'var(--bg-card)'
          e.currentTarget.style.borderColor = isPendingPick
            ? accent
            : isWinner
            ? `${accent}60`
            : 'var(--border-subtle)'
        }
      }}
    >
      <span
        className="font-mono font-bold min-w-[20px] text-xs text-center"
        style={{ color: isLoser ? 'var(--text-muted)' : accent, opacity: isLoser ? 0.5 : 0.8 }}
      >
        {team?.seed || ''}
      </span>
      <span
        className="flex-1 px-1.5 text-left whitespace-nowrap overflow-hidden text-ellipsis font-semibold text-sm"
        style={{
          color: team
            ? isWinner || isPendingPick
              ? accent
              : isLoser
              ? 'var(--text-muted)'
              : 'var(--text-primary)'
            : 'var(--text-muted)',
          textDecoration: isLoser ? 'line-through' : 'none',
        }}
      >
        {team?.name || 'TBD'}
      </span>
      {isWinner && (
        <span className="text-xs font-bold" style={{ color: accent }}>
          W
        </span>
      )}
      {isPendingPick && !isWinner && (
        <span className="text-[10px] font-mono" style={{ color: accent }}>
          PICK
        </span>
      )}
    </button>
  )
}

/* ── Single matchup: two teams, click to pick winner ── */
function PickableMatchup({ game, accent, onSelect, pendingPick, isSubmitting, pruneResult }) {
  const bothTeamsReady = game.teamA && game.teamB
  const isPickable = bothTeamsReady && !game.winner && !isSubmitting
  const isPendingA = pendingPick?.gameId === game.id && pendingPick?.winner?.seed === game.teamA?.seed
  const isPendingB = pendingPick?.gameId === game.id && pendingPick?.winner?.seed === game.teamB?.seed
  const isLoserA = game.winner && game.teamA && game.winner.seed !== game.teamA.seed
  const isLoserB = game.winner && game.teamB && game.winner.seed !== game.teamB.seed

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        border: (isPendingA || isPendingB)
          ? `2px solid ${accent}`
          : game.winner
          ? `1px solid ${accent}40`
          : '1px solid var(--border-subtle)',
        boxShadow: game.winner ? `0 0 12px ${accent}10` : 'none',
        opacity: isSubmitting ? 0.6 : 1,
      }}
    >
      <PickableTeam
        team={game.teamA}
        isWinner={game.winner?.seed === game.teamA?.seed}
        isLoser={isLoserA}
        isPendingPick={isPendingA}
        isPickable={isPickable}
        onClick={() => onSelect(game, game.teamA, game.teamB)}
        accent={accent}
      />
      <PickableTeam
        team={game.teamB}
        isWinner={game.winner?.seed === game.teamB?.seed}
        isLoser={isLoserB}
        isPendingPick={isPendingB}
        isPickable={isPickable}
        onClick={() => onSelect(game, game.teamB, game.teamA)}
        accent={accent}
      />
      {/* Pruning stats — shown after submission */}
      {game.winner && pruneResult && (
        <div
          className="px-2.5 py-1.5 flex items-center justify-between"
          style={{
            background: 'rgba(0,0,0,0.25)',
            borderTop: `1px solid ${accent}30`,
          }}
        >
          <span
            className="text-[9px] font-mono font-bold tracking-[0.15em]"
            style={{ color: accent }}
          >
            LOCKED
          </span>
          <span className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--red-dead, #ef4444)' }}>
              {pruneResult.eliminated.toLocaleString()}
            </span>
            {' out · '}
            <span style={{ color: 'var(--green-alive, #22c55e)' }}>
              {pruneResult.remaining.toLocaleString()}
            </span>
            {' alive'}
          </span>
        </div>
      )}
      {/* Locked indicator for hydrated (pre-existing) results without stats */}
      {game.winner && !pruneResult && (
        <div
          className="px-2.5 py-1 text-center"
          style={{
            background: 'rgba(0,0,0,0.15)',
            borderTop: `1px solid ${accent}20`,
          }}
        >
          <span
            className="text-[9px] font-mono tracking-[0.15em]"
            style={{ color: `${accent}90` }}
          >
            CONFIRMED
          </span>
        </div>
      )}
    </div>
  )
}

/* ── Region bracket picker ── */
function RegionPicker({ region, regionGames, onSelect, pendingPick, isSubmitting, pruneResults }) {
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
                onSelect={onSelect}
                pendingPick={pendingPick}
                isSubmitting={isSubmitting}
                pruneResult={pruneResults?.[`${region}-${game.id}`]}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Final Four picker ── */
function FinalFourPicker({ finalFourGames, onSelect, pendingPick, isSubmitting, pruneResults }) {
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
              onSelect={onSelect}
              pendingPick={pendingPick}
              isSubmitting={isSubmitting}
              pruneResult={pruneResults?.[`f4-${game.id}`]}
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
            onSelect={onSelect}
            pendingPick={pendingPick}
            isSubmitting={isSubmitting}
            pruneResult={pruneResults?.[`f4-${finalFourGames[2].id}`]}
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

  // Auth state — admin key must be verified before showing bracket
  const [authenticated, setAuthenticated] = useState(false)
  const [authError, setAuthError] = useState(null)
  // Start in checking state if we have a stored key (prevents login flash)
  const [authChecking, setAuthChecking] = useState(!!adminKey)

  // Fetch bracket data for team names (only after auth)
  const { data: bracketData } = useQuery({
    queryKey: ['bracket'],
    queryFn: fetchBracket,
    enabled: authenticated,
  })

  // Fetch existing game results (for persistence across page refreshes)
  const { data: existingResults } = useQuery({
    queryKey: ['results', adminKey],
    queryFn: () => fetchResults(adminKey),
    enabled: authenticated,
    staleTime: Infinity,
    retry: false,
  })

  // Game state per region: { South: [...15 games], East: [...], ... }
  const [regionGamesMap, setRegionGamesMap] = useState({})
  const [hydrated, setHydrated] = useState(false)
  // Final four games: [semi1, semi2, championship]
  const [finalFourGames, setFinalFourGames] = useState([
    { id: 'f4-0', round: 'F4', gameNum: 1, teamA: null, teamB: null, winner: null },
    { id: 'f4-1', round: 'F4', gameNum: 2, teamA: null, teamB: null, winner: null },
    { id: 'f4-2', round: 'Championship', gameNum: 1, teamA: null, teamB: null, winner: null },
  ])
  // Pending pick: { gameId, region, game, winner, loser } — selected but not submitted
  const [pendingPick, setPendingPick] = useState(null)
  const [statusMsg, setStatusMsg] = useState(null)
  const [activeRegion, setActiveRegion] = useState('South')
  // Pruning results per game: { "South-3": { eliminated, remaining }, "f4-f4-0": {...} }
  const [pruneResults, setPruneResults] = useState({})

  // Auto-authenticate on mount if adminKey already exists in localStorage
  useEffect(() => {
    if (adminKey && !authenticated) {
      setAuthChecking(true)
      fetchResults(adminKey)
        .then(() => setAuthenticated(true))
        .catch(() => {}) // silent — user will see login screen
        .finally(() => setAuthChecking(false))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Verify admin key by hitting the results endpoint
  const handleLogin = async () => {
    if (!adminKey.trim()) {
      setAuthError('Enter an admin key.')
      return
    }
    setAuthChecking(true)
    setAuthError(null)
    try {
      await fetchResults(adminKey)
      setAuthenticated(true)
    } catch {
      setAuthError('Invalid admin key.')
    } finally {
      setAuthChecking(false)
    }
  }

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

  const currentRegionGames = initializedRegions

  // Update final four teams when region champions change
  const currentFinalFour = useMemo(() => {
    const southChamp = currentRegionGames.South?.[14]?.winner || null
    const eastChamp = currentRegionGames.East?.[14]?.winner || null
    const westChamp = currentRegionGames.West?.[14]?.winner || null
    const midwestChamp = currentRegionGames.Midwest?.[14]?.winner || null

    const updated = finalFourGames.map((g) => ({ ...g }))

    updated[0] = { ...updated[0], teamA: southChamp, teamB: eastChamp }
    updated[1] = { ...updated[1], teamA: westChamp, teamB: midwestChamp }
    updated[2] = {
      ...updated[2],
      teamA: updated[0].winner || null,
      teamB: updated[1].winner || null,
    }

    if (
      updated[2].winner &&
      (updated[2].teamA?.seed !== finalFourGames[2].teamA?.seed ||
        updated[2].teamB?.seed !== finalFourGames[2].teamB?.seed)
    ) {
      updated[2] = { ...updated[2], winner: null }
    }

    return updated
  }, [currentRegionGames, finalFourGames])

  // Hydrate bracket state from existing game results on load
  useEffect(() => {
    if (!bracketData?.regions || !existingResults || hydrated) return
    if (existingResults.length === 0) {
      setHydrated(true)
      return
    }

    const freshRegions = {}
    for (const region of REGIONS) {
      const teams = bracketData.regions[region] || []
      freshRegions[region] = buildRegionGames(teams)
    }

    const regionalResults = existingResults.filter(
      (r) => r.region && REGIONS.includes(r.region)
    )
    for (const result of regionalResults) {
      const offset = ROUND_OFFSET[result.round]
      if (offset === undefined) continue
      const gameId = offset + result.game_number
      const games = freshRegions[result.region]
      if (!games || !games[gameId]) continue

      const game = games[gameId]
      const winner =
        game.teamA?.seed === result.winner_seed ? game.teamA :
        game.teamB?.seed === result.winner_seed ? game.teamB :
        null
      if (winner) {
        games[gameId] = { ...games[gameId], winner }
        freshRegions[result.region] = propagateWinners(games)
      }
    }

    setRegionGamesMap(freshRegions)

    const f4Results = existingResults.filter((r) => r.round === 'F4' || r.round === 'Final')
    if (f4Results.length > 0) {
      const updatedFF = [
        { ...finalFourGames[0] },
        { ...finalFourGames[1] },
        { ...finalFourGames[2] },
      ]

      const southChamp = freshRegions.South?.[14]?.winner || null
      const eastChamp = freshRegions.East?.[14]?.winner || null
      const westChamp = freshRegions.West?.[14]?.winner || null
      const midwestChamp = freshRegions.Midwest?.[14]?.winner || null

      updatedFF[0].teamA = southChamp
      updatedFF[0].teamB = eastChamp
      updatedFF[1].teamA = westChamp
      updatedFF[1].teamB = midwestChamp

      for (const result of f4Results) {
        if (result.round === 'F4') {
          const game = updatedFF[result.game_number]
          if (game) {
            const winner =
              game.teamA?.seed === result.winner_seed && game.teamA?.name === result.winner_name ? game.teamA :
              game.teamB?.seed === result.winner_seed && game.teamB?.name === result.winner_name ? game.teamB :
              game.teamA?.seed === result.winner_seed ? game.teamA :
              game.teamB?.seed === result.winner_seed ? game.teamB :
              null
            if (winner) {
              updatedFF[result.game_number] = { ...updatedFF[result.game_number], winner }
              updatedFF[2] = {
                ...updatedFF[2],
                [result.game_number === 0 ? 'teamA' : 'teamB']: winner,
              }
            }
          }
        } else if (result.round === 'Final') {
          const game = updatedFF[2]
          const winner =
            game.teamA?.name === result.winner_name ? game.teamA :
            game.teamB?.name === result.winner_name ? game.teamB :
            game.teamA?.seed === result.winner_seed ? game.teamA :
            game.teamB?.seed === result.winner_seed ? game.teamB :
            null
          if (winner) {
            updatedFF[2] = { ...updatedFF[2], winner }
          }
        }
      }

      setFinalFourGames(updatedFF)
    }

    setHydrated(true)
  }, [bracketData, existingResults, hydrated])

  const mutation = useMutation({
    mutationFn: (data) => submitResult(data, adminKey),
    onSuccess: (result) => {
      const eliminated = result.eliminated ?? 0
      const remaining = result.alive_remaining ?? 0
      // Store pruning stats for the game card indicator
      if (pendingPick) {
        const gameKey = pendingPick.region === 'Final Four'
          ? `f4-${pendingPick.gameId}`
          : `${pendingPick.region}-${pendingPick.gameId}`
        setPruneResults((prev) => ({ ...prev, [gameKey]: { eliminated, remaining } }))
      }
      setStatusMsg({
        type: 'success',
        text: `${result.game} — ${eliminated.toLocaleString()} brackets eliminated, ${remaining.toLocaleString()} remaining.`,
      })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['brackets'] })
      queryClient.invalidateQueries({ queryKey: ['bracket'] })
      setPendingPick(null)
    },
    onError: (err) => {
      // Revert local bracket state on failure
      if (pendingPick) {
        revertPick(pendingPick)
      }
      setStatusMsg({ type: 'error', text: err.message })
      setPendingPick(null)
    },
  })

  // Revert a pending pick that failed submission
  const revertPick = (pick) => {
    if (pick.region && pick.region !== 'Final Four') {
      // Undo the local region game winner
      const games = currentRegionGames[pick.region]
      if (games) {
        const reverted = games.map((g) =>
          g.id === pick.gameId ? { ...g, winner: null } : g
        )
        setRegionGamesMap((prev) => ({ ...prev, [pick.region]: propagateWinners(reverted) }))
      }
    } else {
      // Undo F4/Championship pick
      setFinalFourGames((prev) => prev.map((g) =>
        g.id === pick.gameId ? { ...g, winner: null } : g
      ))
    }
  }

  // Step 1: User clicks a team — just stage the pick, don't submit
  const handleSelect = (region, game, winner, loser) => {
    // If clicking the same pending pick, deselect it
    if (pendingPick?.gameId === game.id && pendingPick?.winner?.seed === winner.seed) {
      setPendingPick(null)
      return
    }
    setPendingPick({ gameId: game.id, region, game, winner, loser })
    setStatusMsg(null)
  }

  const handleSelectFinalFour = (game, winner, loser) => {
    if (pendingPick?.gameId === game.id && pendingPick?.winner?.seed === winner.seed) {
      setPendingPick(null)
      return
    }
    setPendingPick({ gameId: game.id, region: 'Final Four', game, winner, loser })
    setStatusMsg(null)
  }

  // Step 2: User clicks Submit — apply to local state + fire API
  const handleConfirmPick = () => {
    if (!pendingPick) return
    const { region, game, winner, loser } = pendingPick

    if (region === 'Final Four') {
      // Apply to local F4 state
      const updatedFF = currentFinalFour.map((g) =>
        g.id === game.id ? { ...g, winner } : g
      )
      if (game.round === 'F4') {
        const idx = game.id === 'f4-0' ? 0 : 1
        updatedFF[2] = {
          ...updatedFF[2],
          [idx === 0 ? 'teamA' : 'teamB']: winner,
        }
      }
      setFinalFourGames(updatedFF)

      mutation.mutate({
        region: '',
        round: game.round === 'Championship' ? 'Final' : game.round,
        game_index: game.id === 'f4-0' ? 0 : game.id === 'f4-1' ? 1 : 0,
        winner_seed: winner.seed,
        loser_seed: loser.seed,
        winner_name: winner.name,
        loser_name: loser.name,
      })
    } else {
      // Apply to local region state
      const updatedGames = currentRegionGames[region].map((g) =>
        g.id === game.id ? { ...g, winner } : g
      )
      setRegionGamesMap((prev) => ({ ...prev, [region]: propagateWinners(updatedGames) }))

      mutation.mutate({
        region,
        round: game.round,
        game_index: game.gameNum - 1,
        winner_seed: winner.seed,
        loser_seed: loser.seed,
        winner_name: winner.name,
        loser_name: loser.name,
      })
    }
  }

  const handleCancelPick = () => {
    setPendingPick(null)
  }

  // Count completed games
  const completedCount = REGIONS.reduce((sum, region) => {
    const games = currentRegionGames[region] || []
    return sum + games.filter((g) => g.winner).length
  }, 0) + currentFinalFour.filter((g) => g.winner).length

  const MOBILE_TABS = [...REGIONS, 'Final Four']

  // ── Gate: show login screen if not authenticated ──
  if (!authenticated) {
    // Show loading spinner during auto-auth (prevents login form flash)
    if (authChecking && adminKey) {
      return (
        <div className="max-w-md mx-auto mt-20 text-center space-y-3">
          <h2 className="font-display text-3xl tracking-wider" style={{ color: 'var(--orange)' }}>
            BRACKET CONTROL
          </h2>
          <p className="text-xs font-mono animate-pulse" style={{ color: 'var(--text-muted)' }}>
            VERIFYING ACCESS...
          </p>
        </div>
      )
    }
    return (
      <div className="max-w-md mx-auto mt-20 space-y-5">
        <div className="text-center">
          <h2 className="font-display text-3xl tracking-wider" style={{ color: 'var(--orange)' }}>
            BRACKET CONTROL
          </h2>
          <p className="text-xs font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
            ADMIN ACCESS REQUIRED
          </p>
        </div>

        <div className="glass rounded-xl p-6 space-y-4" style={{ border: '1px solid var(--border-subtle)' }}>
          <label
            className="block text-[10px] font-mono uppercase tracking-[0.2em]"
            style={{ color: 'var(--text-muted)' }}
          >
            Admin Key
          </label>
          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            placeholder="Enter admin key..."
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none transition-all duration-200 focus:ring-1"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              '--tw-ring-color': 'var(--orange)',
            }}
            autoFocus
          />
          {authError && (
            <p className="text-xs font-mono" style={{ color: 'var(--red-dead)' }}>
              {authError}
            </p>
          )}
          <button
            onClick={handleLogin}
            disabled={authChecking}
            className="w-full py-2.5 rounded-lg font-mono text-sm font-bold tracking-wider transition-all duration-200"
            style={{
              backgroundColor: authChecking ? 'var(--bg-card)' : 'var(--orange)',
              color: authChecking ? 'var(--text-muted)' : 'white',
              opacity: authChecking ? 0.6 : 1,
            }}
          >
            {authChecking ? 'VERIFYING...' : 'UNLOCK'}
          </button>
        </div>
      </div>
    )
  }

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

      {/* Confirmation bar — shown when a pick is staged */}
      {pendingPick && (
        <div
          className="rounded-xl p-4 flex flex-col sm:flex-row items-center gap-3"
          style={{
            background: 'linear-gradient(90deg, rgba(255,107,53,0.12), rgba(255,107,53,0.04))',
            border: '2px solid var(--orange)',
          }}
        >
          <div className="flex-1 text-center sm:text-left">
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] block" style={{ color: 'var(--text-muted)' }}>
              CONFIRM RESULT — {pendingPick.region === 'Final Four' ? pendingPick.game.round : `${pendingPick.region} ${pendingPick.game.round}`}
            </span>
            <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              ({pendingPick.winner.seed}) {pendingPick.winner.name}
              <span style={{ color: 'var(--text-muted)' }}> beats </span>
              ({pendingPick.loser.seed}) {pendingPick.loser.name}
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCancelPick}
              disabled={mutation.isPending}
              className="px-4 py-2 rounded-lg font-mono text-xs font-bold tracking-wider transition-all duration-200"
              style={{
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              CANCEL
            </button>
            <button
              onClick={handleConfirmPick}
              disabled={mutation.isPending}
              className="px-5 py-2 rounded-lg font-mono text-xs font-bold tracking-wider transition-all duration-200"
              style={{
                backgroundColor: mutation.isPending ? 'var(--bg-card)' : 'var(--orange)',
                color: mutation.isPending ? 'var(--text-muted)' : 'white',
                opacity: mutation.isPending ? 0.6 : 1,
              }}
            >
              {mutation.isPending ? 'SUBMITTING...' : 'SUBMIT RESULT'}
            </button>
          </div>
        </div>
      )}

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
            onSelect={(game, winner, loser) => handleSelectFinalFour(game, winner, loser)}
            pendingPick={pendingPick}
            isSubmitting={mutation.isPending}
            pruneResults={pruneResults}
          />
        ) : (
          <RegionPicker
            region={activeRegion}
            regionGames={currentRegionGames[activeRegion] || []}
            onSelect={(game, winner, loser) => handleSelect(activeRegion, game, winner, loser)}
            pendingPick={pendingPick}
            isSubmitting={mutation.isPending}
            pruneResults={pruneResults}
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
            Click a team to select them as the winner.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>02</span>
            Review the pick in the confirmation bar, then click SUBMIT RESULT.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>03</span>
            Brackets with wrong picks are eliminated. Winners advance automatically.
          </p>
        </div>
      </div>
    </div>
  )
}
