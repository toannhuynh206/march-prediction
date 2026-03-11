/**
 * Bracket Explorer: paginated list of 10M brackets — dark broadcast table.
 * Uses cursor-based (keyset) pagination for efficient traversal.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBrackets, fetchBracketDetail } from '../api/client'
import useTournamentStore from '../store/tournamentStore'

function BracketRow({ bracket, isExpanded, onToggle, index }) {
  const upsetColor =
    bracket.upset_count > 10
      ? 'var(--red-dead)'
      : bracket.upset_count > 6
        ? 'var(--orange)'
        : 'var(--green-alive)'

  return (
    <>
      <div
        onClick={onToggle}
        className="grid grid-cols-[40px_1fr_60px_40px] sm:grid-cols-[50px_1fr_90px_80px_80px_50px] items-center px-2 sm:px-4 py-3 cursor-pointer transition-all duration-150 glass-hover"
        style={{
          borderBottom: '1px solid var(--border-subtle)',
          animationDelay: `${index * 30}ms`,
        }}
      >
        <span className="font-mono text-xs font-bold" style={{ color: 'var(--text-muted)' }}>
          #{bracket.rank}
        </span>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
            {bracket.champion}
          </span>
          <span
            className="font-mono text-[10px] px-1.5 py-0.5 rounded"
            style={{
              color: 'var(--orange)',
              background: 'var(--orange-glow)',
              border: '1px solid rgba(255,107,53,0.2)',
            }}
          >
            {bracket.champion_seed}
          </span>
        </div>
        <span className="text-right font-mono text-sm font-bold" style={{ color: 'var(--orange)' }}>
          {bracket.expected_score}
        </span>
        <span className="text-right font-mono text-xs hidden sm:block" style={{ color: 'var(--text-secondary)' }}>
          {(bracket.probability * 100).toFixed(4)}%
        </span>
        <span className="text-right font-mono text-xs font-semibold hidden sm:block" style={{ color: upsetColor }}>
          {bracket.upset_count} upsets
        </span>
        <div className="flex justify-center">
          {bracket.is_alive ? (
            <span
              className="w-2.5 h-2.5 rounded-full pulse-dot"
              style={{ backgroundColor: 'var(--green-alive)' }}
              title="Alive"
            />
          ) : (
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: 'var(--red-dead)', opacity: 0.6 }}
              title="Eliminated"
            />
          )}
        </div>
      </div>
      {isExpanded && <BracketDetail bracketId={bracket.id} />}
    </>
  )
}

function BracketDetail({ bracketId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['bracket-detail', bracketId],
    queryFn: () => fetchBracketDetail(bracketId),
  })

  if (isLoading) {
    return (
      <div className="p-6 text-center" style={{ background: 'rgba(255,107,53,0.03)', borderBottom: '1px solid var(--border-accent)' }}>
        <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>Loading bracket...</span>
      </div>
    )
  }
  if (error) {
    return (
      <div className="p-4 text-center text-sm" style={{ color: 'var(--red-dead)', background: 'rgba(239,68,68,0.05)' }}>
        Error: {error.message}
      </div>
    )
  }

  const REGION_ACCENT = { South: '#FF6B35', East: '#00D4FF', West: '#F59E0B', Midwest: '#22C55E' }

  return (
    <div
      className="p-4 animate-fade-up"
      style={{ background: 'rgba(255,107,53,0.03)', borderBottom: '2px solid var(--border-accent)' }}
    >
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(data.regions || {}).map(([region, picks]) => {
          const accent = REGION_ACCENT[region] || 'var(--orange)'
          return (
            <div key={region} className="glass rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1 h-4 rounded-full" style={{ backgroundColor: accent }} />
                <span className="text-[11px] font-display tracking-wider" style={{ color: accent }}>
                  {region.toUpperCase()}
                </span>
                <span className="text-[9px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
                  {picks.champion?.name} ({picks.champion?.seed})
                </span>
              </div>
              <div className="space-y-0.5">
                {(picks.R64 || []).map((g, i) => (
                  <div key={i} className="flex items-center text-[10px] gap-1.5 py-0.5">
                    <span
                      className="flex-1 font-medium"
                      style={{ color: g.upset ? 'var(--orange)' : 'var(--text-secondary)' }}
                    >
                      {g.upset && (
                        <span className="text-[8px] mr-1 font-black" style={{ color: 'var(--orange)' }}>!</span>
                      )}
                      {g.winner}
                    </span>
                    <span className="font-mono text-[9px]" style={{ color: 'var(--text-muted)' }}>
                      {g.seeds[0]}v{g.seeds[1]}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
      {data.final_four && (
        <div
          className="mt-3 glass rounded-lg p-3 text-center"
          style={{ border: '1px solid var(--border-accent)' }}
        >
          <span className="font-display text-sm tracking-wider" style={{ color: 'var(--orange)' }}>
            CHAMPION: {data.final_four.championship?.winner}
          </span>
        </div>
      )}
    </div>
  )
}

export default function ExplorerPage() {
  const { explorerSort, explorerAliveOnly, setExplorerSort, setExplorerAliveOnly } = useTournamentStore()
  const [cursors, setCursors] = useState([null])
  const [pageIndex, setPageIndex] = useState(0)
  const [expandedId, setExpandedId] = useState(null)

  const currentCursor = cursors[pageIndex]

  const { data, isLoading, error } = useQuery({
    queryKey: ['brackets', currentCursor, explorerSort, explorerAliveOnly],
    queryFn: () =>
      fetchBrackets({
        cursor: currentCursor,
        sort: explorerSort,
        aliveOnly: explorerAliveOnly,
      }),
    keepPreviousData: true,
  })

  const goNext = () => {
    if (data?.cursor) {
      const newCursors = [...cursors]
      if (pageIndex + 1 >= newCursors.length) {
        newCursors.push(data.cursor)
      }
      setCursors(newCursors)
      setPageIndex(pageIndex + 1)
    }
  }

  const goPrev = () => {
    if (pageIndex > 0) {
      setPageIndex(pageIndex - 1)
    }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-mono uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Sort
          </label>
          <select
            value={explorerSort}
            onChange={(e) => {
              setExplorerSort(e.target.value)
              setCursors([null])
              setPageIndex(0)
            }}
            className="text-sm font-medium rounded-lg px-3 py-1.5 border-none outline-none cursor-pointer"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <option value="score">Expected Score</option>
            <option value="probability">Probability</option>
          </select>
        </div>

        <label className="flex items-center gap-2 cursor-pointer group">
          <input
            type="checkbox"
            checked={explorerAliveOnly}
            onChange={(e) => {
              setExplorerAliveOnly(e.target.checked)
              setCursors([null])
              setPageIndex(0)
            }}
            className="rounded accent-orange-500"
          />
          <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            Alive only
          </span>
        </label>

        {data && (
          <div className="ml-auto flex items-center gap-3">
            <span className="font-mono text-xs" style={{ color: 'var(--green-alive)' }}>
              {data.alive_count.toLocaleString()} alive
            </span>
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              / {data.total.toLocaleString()} total
            </span>
          </div>
        )}
      </div>

      {/* Bracket list */}
      <div className="glass rounded-xl overflow-hidden">
        {/* Header */}
        <div
          className="grid grid-cols-[40px_1fr_60px_40px] sm:grid-cols-[50px_1fr_90px_80px_80px_50px] items-center px-2 sm:px-4 py-3 text-[10px] font-mono uppercase tracking-widest"
          style={{
            color: 'var(--text-muted)',
            background: 'rgba(255,255,255,0.02)',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <span>Rank</span>
          <span>Champion</span>
          <span className="text-right">E[Score]</span>
          <span className="text-right hidden sm:block">Prob</span>
          <span className="text-right hidden sm:block">Upsets</span>
          <span className="text-center">Live</span>
        </div>

        {isLoading && (
          <div className="p-12 text-center">
            <div className="w-8 h-8 mx-auto mb-3 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--orange)', borderTopColor: 'transparent' }} />
            <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>LOADING BRACKETS...</span>
          </div>
        )}

        {error && (
          <div className="p-8 text-center" style={{ color: 'var(--red-dead)' }}>
            Error: {error.message}
          </div>
        )}

        {data?.brackets?.length === 0 && (
          <div className="p-12 text-center">
            <span className="text-3xl mb-3 block">🏀</span>
            <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
              No brackets found. Run the simulation first.
            </span>
          </div>
        )}

        {data?.brackets?.map((b, i) => (
          <BracketRow
            key={b.id}
            bracket={{ ...b, rank: b.rank + pageIndex * 50 }}
            isExpanded={expandedId === b.id}
            onToggle={() => setExpandedId(expandedId === b.id ? null : b.id)}
            index={i}
          />
        ))}
      </div>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="glass rounded-xl p-3 flex items-center justify-between">
          <button
            onClick={goPrev}
            disabled={pageIndex === 0}
            className="px-5 py-2 rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:opacity-20"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            ← PREV
          </button>
          <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
            PAGE {pageIndex + 1}
          </span>
          <button
            onClick={goNext}
            disabled={!data.has_more}
            className="px-5 py-2 rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:opacity-20"
            style={{
              backgroundColor: 'var(--orange)',
              color: 'white',
              border: 'none',
              boxShadow: data.has_more ? '0 0 20px rgba(255,107,53,0.2)' : 'none',
            }}
          >
            NEXT →
          </button>
        </div>
      )}
    </div>
  )
}
