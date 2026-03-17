/**
 * BracketView: Browse individual generated brackets one at a time.
 * Prev/Next navigation with team champion filter and sort controls.
 */

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBrackets, fetchBracketDetail, fetchBracket, fetchGameResults } from '../api/client'
import useTournamentStore from '../store/tournamentStore'
import BracketDetailView from './BracketDetailView'

function TeamFilterSelect({ value, onChange, teams }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="text-sm font-medium rounded-lg px-3 py-1.5 border-none outline-none cursor-pointer"
      style={{
        backgroundColor: 'var(--bg-card)',
        color: value ? 'var(--orange)' : 'var(--text-primary)',
        border: `1px solid ${value ? 'var(--border-accent)' : 'var(--border-subtle)'}`,
      }}
    >
      <option value="">All Champions</option>
      {teams.map((t) => (
        <option key={`${t.name}-${t.region}`} value={t.name}>
          ({t.seed}) {t.name} — {t.region}
        </option>
      ))}
    </select>
  )
}

function BracketNavButton({ onClick, disabled, children, primary }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-5 py-2.5 rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:opacity-20"
      style={{
        backgroundColor: primary ? 'var(--orange)' : 'var(--bg-card)',
        color: primary ? 'white' : 'var(--text-primary)',
        border: primary ? 'none' : '1px solid var(--border-subtle)',
        boxShadow: primary && !disabled ? '0 0 20px rgba(255,107,53,0.2)' : 'none',
      }}
    >
      {children}
    </button>
  )
}

function BracketMeta({ bracket }) {
  if (!bracket) return null

  const upsetColor =
    bracket.upset_count > 10
      ? 'var(--red-dead)'
      : bracket.upset_count > 6
        ? 'var(--orange)'
        : 'var(--green-alive)'

  return (
    <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
      <div className="flex items-center gap-1.5">
        <span style={{ color: 'var(--text-muted)' }}>RANK</span>
        <span className="font-bold" style={{ color: 'var(--text-primary)' }}>#{bracket.rank}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span style={{ color: 'var(--text-muted)' }}>PROB</span>
        <span className="font-bold" style={{ color: 'var(--orange)' }}>
          {(bracket.probability * 100).toFixed(6)}%
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span style={{ color: 'var(--text-muted)' }}>WEIGHT</span>
        <span style={{ color: 'var(--text-secondary)' }}>{bracket.expected_score}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span style={{ color: 'var(--text-muted)' }}>UPSETS</span>
        <span className="font-semibold" style={{ color: upsetColor }}>
          {bracket.upset_count}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        {bracket.is_alive ? (
          <>
            <span
              className="w-2 h-2 rounded-full pulse-dot"
              style={{ backgroundColor: 'var(--green-alive)' }}
            />
            <span style={{ color: 'var(--green-alive)' }}>ALIVE</span>
          </>
        ) : (
          <>
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--red-dead)', opacity: 0.6 }}
            />
            <span style={{ color: 'var(--red-dead)' }}>ELIMINATED</span>
          </>
        )}
      </div>
    </div>
  )
}

function BracketFullDetail({ bracketId, gameResults }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['bracket-detail', bracketId],
    queryFn: () => fetchBracketDetail(bracketId),
  })

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-3 py-16">
        <div
          className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--orange)', borderTopColor: 'transparent' }}
        />
        <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
          LOADING BRACKET...
        </span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 text-center text-sm" style={{ color: 'var(--red-dead)' }}>
        Error: {error.message}
      </div>
    )
  }

  return <BracketDetailView data={data} gameResults={gameResults} />
}

export default function BracketView() {
  const {
    bracketSort, bracketChampion,
    setBracketSort, setBracketChampion,
  } = useTournamentStore()

  const [cursors, setCursors] = useState([null])
  const [pageIndex, setPageIndex] = useState(0)
  const [bracketIndex, setBracketIndex] = useState(0)

  const PAGE_SIZE = 50

  // Fetch team list for the filter dropdown
  const { data: bracketData } = useQuery({
    queryKey: ['bracket'],
    queryFn: fetchBracket,
  })

  // Fetch actual game results for bust indicators
  const { data: gameResults } = useQuery({
    queryKey: ['game-results'],
    queryFn: fetchGameResults,
    refetchInterval: 30_000,
    staleTime: 30_000,
  })

  const allTeams = useMemo(() => {
    if (!bracketData?.regions) return []
    const teams = []
    for (const [, regionTeams] of Object.entries(bracketData.regions)) {
      for (const t of regionTeams) {
        teams.push({ name: t.name, seed: t.seed, region: t.region })
      }
    }
    return teams.sort((a, b) => a.seed - b.seed || a.name.localeCompare(b.name))
  }, [bracketData])

  const currentCursor = cursors[pageIndex]

  // Fetch current page of brackets
  const { data, isLoading, error } = useQuery({
    queryKey: ['bracket-viewer', currentCursor, bracketSort, bracketChampion],
    queryFn: () =>
      fetchBrackets({
        cursor: currentCursor,
        limit: PAGE_SIZE,
        sort: bracketSort,
        champion: bracketChampion,
      }),
    keepPreviousData: true,
  })

  const brackets = data?.brackets || []
  const currentBracket = brackets[bracketIndex]
  const globalRank = pageIndex * PAGE_SIZE + bracketIndex + 1

  const canGoPrev = pageIndex > 0 || bracketIndex > 0
  const canGoNext = bracketIndex < brackets.length - 1 || data?.has_more

  const goNext = () => {
    if (bracketIndex < brackets.length - 1) {
      setBracketIndex(bracketIndex + 1)
    } else if (data?.has_more && data?.cursor) {
      const newCursors = [...cursors]
      if (pageIndex + 1 >= newCursors.length) {
        newCursors.push(data.cursor)
      }
      setCursors(newCursors)
      setPageIndex(pageIndex + 1)
      setBracketIndex(0)
    }
  }

  const goPrev = () => {
    if (bracketIndex > 0) {
      setBracketIndex(bracketIndex - 1)
    } else if (pageIndex > 0) {
      setPageIndex(pageIndex - 1)
      setBracketIndex(PAGE_SIZE - 1)
    }
  }

  const resetPagination = () => {
    setCursors([null])
    setPageIndex(0)
    setBracketIndex(0)
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label
            className="text-[10px] font-mono uppercase tracking-widest"
            style={{ color: 'var(--text-muted)' }}
          >
            Sort
          </label>
          <select
            value={bracketSort}
            onChange={(e) => {
              setBracketSort(e.target.value)
              resetPagination()
            }}
            className="text-sm font-medium rounded-lg px-3 py-1.5 border-none outline-none cursor-pointer"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <option value="probability">Probability</option>
            <option value="score">Expected Score</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label
            className="text-[10px] font-mono uppercase tracking-widest"
            style={{ color: 'var(--text-muted)' }}
          >
            Champion
          </label>
          <TeamFilterSelect
            value={bracketChampion}
            onChange={(team) => {
              setBracketChampion(team)
              resetPagination()
            }}
            teams={allTeams}
          />
        </div>

        {data && (
          <div className="ml-auto flex items-center gap-3">
            <span className="font-mono text-xs" style={{ color: 'var(--green-alive)' }}>
              {data.alive_count.toLocaleString()} / {data.total.toLocaleString()} alive
            </span>
          </div>
        )}
      </div>

      {/* Bracket viewer */}
      <div className="glass rounded-xl overflow-hidden">
        {isLoading && !currentBracket && (
          <div className="flex flex-col items-center gap-3 py-16">
            <div
              className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: 'var(--orange)', borderTopColor: 'transparent' }}
            />
            <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
              LOADING BRACKETS...
            </span>
          </div>
        )}

        {error && (
          <div className="p-8 text-center" style={{ color: 'var(--red-dead)' }}>
            Error: {error.message}
          </div>
        )}

        {brackets.length === 0 && !isLoading && (
          <div className="p-12 text-center">
            <span className="text-3xl mb-3 block">&#x1F3C0;</span>
            <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
              {bracketChampion
                ? `No brackets found with ${bracketChampion} as champion.`
                : 'No brackets found. Run the simulation first.'}
            </span>
          </div>
        )}

        {currentBracket && (
          <>
            {/* Bracket header with meta info */}
            <div
              className="px-4 py-3 flex flex-wrap items-center justify-between gap-3"
              style={{
                background: 'rgba(255,255,255,0.02)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div className="flex items-center gap-3">
                <span
                  className="font-display text-lg tracking-wider"
                  style={{ color: 'var(--text-primary)' }}
                >
                  BRACKET #{globalRank}
                </span>
                <span
                  className="font-mono text-xs px-2 py-0.5 rounded"
                  style={{
                    color: 'var(--orange)',
                    background: 'var(--orange-glow)',
                    border: '1px solid rgba(255,107,53,0.2)',
                  }}
                >
                  {currentBracket.champion} ({currentBracket.champion_seed})
                </span>
              </div>
              <BracketMeta bracket={currentBracket} />
            </div>

            {/* Full bracket visualization */}
            <div className="p-4">
              <BracketFullDetail bracketId={currentBracket.id} gameResults={gameResults} />
            </div>
          </>
        )}
      </div>

      {/* Navigation */}
      {data && data.total > 0 && (
        <div className="glass rounded-xl p-3 flex items-center justify-between">
          <BracketNavButton onClick={goPrev} disabled={!canGoPrev}>
            &#8592; PREV
          </BracketNavButton>
          <div className="flex flex-col items-center">
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              BRACKET {globalRank} OF {data.total.toLocaleString()}
            </span>
            <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)', opacity: 0.6 }}>
              Sorted by {bracketSort === 'probability' ? 'probability' : 'expected score'}
              {bracketChampion ? ` | ${bracketChampion}` : ''}
            </span>
          </div>
          <BracketNavButton onClick={goNext} disabled={!canGoNext} primary>
            NEXT &#8594;
          </BracketNavButton>
        </div>
      )}
    </div>
  )
}
