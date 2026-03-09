/**
 * Bracket Explorer: paginated list of 10M brackets with click-to-expand detail.
 * Uses cursor-based (keyset) pagination for efficient traversal.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBrackets, fetchBracketDetail } from '../api/client'
import useTournamentStore from '../store/tournamentStore'

function BracketRow({ bracket, isExpanded, onToggle }) {
  const upsetColor = bracket.upset_count > 10 ? 'text-red-600' : bracket.upset_count > 6 ? 'text-orange-500' : 'text-green-600'
  return (
    <>
      <div
        onClick={onToggle}
        className="grid grid-cols-[60px_1fr_100px_80px_80px_60px] items-center px-3 py-2 border-b border-gray-100 cursor-pointer hover:bg-blue-50/30 transition-colors text-[12px]"
      >
        <span className="font-bold text-gray-400">#{bracket.rank}</span>
        <span className="font-semibold" style={{ color: 'var(--midnight)' }}>
          {bracket.champion}
          <span className="text-[10px] text-gray-400 ml-1">({bracket.champion_seed})</span>
        </span>
        <span className="text-right font-mono font-bold" style={{ color: 'var(--orange)' }}>
          {bracket.expected_score}
        </span>
        <span className="text-right font-mono text-gray-500">
          {(bracket.probability * 100).toFixed(4)}%
        </span>
        <span className={`text-right font-semibold ${upsetColor}`}>
          {bracket.upset_count} upsets
        </span>
        <span className="text-center">
          {bracket.is_alive ? (
            <span className="inline-block w-2 h-2 rounded-full bg-green-500" title="Alive" />
          ) : (
            <span className="inline-block w-2 h-2 rounded-full bg-red-400" title="Eliminated" />
          )}
        </span>
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

  if (isLoading) return <div className="p-4 text-center text-gray-400 text-sm">Loading bracket detail...</div>
  if (error) return <div className="p-4 text-center text-red-500 text-sm">Error: {error.message}</div>

  return (
    <div className="bg-gray-50 p-4 border-b-2 border-blue-200">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(data.regions || {}).map(([region, picks]) => (
          <div key={region} className="bg-white rounded-lg p-3 shadow-sm">
            <div className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--midnight)' }}>
              {region}
              <span className="ml-2 text-[10px] font-normal text-gray-400">
                Champion: {picks.champion?.name} ({picks.champion?.seed})
              </span>
            </div>
            <div className="space-y-0.5">
              {(picks.R64 || []).map((g, i) => (
                <div key={i} className="flex items-center text-[10px] gap-1">
                  <span className={`flex-1 ${g.upset ? 'text-orange-600 font-bold' : 'text-gray-600'}`}>
                    {g.upset && <span className="text-[8px] mr-0.5">!</span>}
                    {g.winner}
                  </span>
                  <span className="text-gray-300 text-[9px]">
                    ({g.seeds[0]}v{g.seeds[1]})
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {data.final_four && (
        <div className="mt-3 bg-white rounded-lg p-3 shadow-sm text-center">
          <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--orange)' }}>
            Champion: {data.final_four.championship?.winner}
          </span>
        </div>
      )}
    </div>
  )
}

export default function ExplorerPage() {
  const { explorerSort, explorerAliveOnly, setExplorerSort, setExplorerAliveOnly } = useTournamentStore()
  const [cursors, setCursors] = useState([null]) // stack of cursors for prev/next
  const [pageIndex, setPageIndex] = useState(0)
  const [expandedId, setExpandedId] = useState(null)

  const currentCursor = cursors[pageIndex]

  const { data, isLoading, error } = useQuery({
    queryKey: ['brackets', currentCursor, explorerSort, explorerAliveOnly],
    queryFn: () => fetchBrackets({
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
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 bg-white rounded-lg shadow-sm p-3">
        <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">Sort by</label>
        <select
          value={explorerSort}
          onChange={(e) => { setExplorerSort(e.target.value); setCursors([null]); setPageIndex(0) }}
          className="text-sm border border-gray-200 rounded px-2 py-1"
        >
          <option value="score">Expected Score</option>
          <option value="probability">Probability</option>
        </select>

        <label className="flex items-center gap-1.5 text-[11px] text-gray-600 ml-4">
          <input
            type="checkbox"
            checked={explorerAliveOnly}
            onChange={(e) => { setExplorerAliveOnly(e.target.checked); setCursors([null]); setPageIndex(0) }}
            className="rounded"
          />
          Alive only
        </label>

        {data && (
          <div className="ml-auto text-[11px] text-gray-400">
            {data.alive_count.toLocaleString()} alive / {data.total.toLocaleString()} total
          </div>
        )}
      </div>

      {/* Bracket list */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[60px_1fr_100px_80px_80px_60px] items-center px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-gray-400 border-b-2 border-gray-100">
          <span>Rank</span>
          <span>Champion</span>
          <span className="text-right">E[Score]</span>
          <span className="text-right">Prob</span>
          <span className="text-right">Upsets</span>
          <span className="text-center">Status</span>
        </div>

        {isLoading && (
          <div className="p-8 text-center text-gray-400">Loading brackets...</div>
        )}

        {error && (
          <div className="p-8 text-center text-red-500">Error: {error.message}</div>
        )}

        {data?.brackets?.length === 0 && (
          <div className="p-8 text-center text-gray-400">No brackets found. Run the simulation first.</div>
        )}

        {data?.brackets?.map((b) => (
          <BracketRow
            key={b.id}
            bracket={{ ...b, rank: b.rank + pageIndex * 50 }}
            isExpanded={expandedId === b.id}
            onToggle={() => setExpandedId(expandedId === b.id ? null : b.id)}
          />
        ))}
      </div>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="flex items-center justify-between bg-white rounded-lg shadow-sm p-3">
          <button
            onClick={goPrev}
            disabled={pageIndex === 0}
            className="px-4 py-1.5 rounded text-sm font-semibold disabled:opacity-30 transition-colors"
            style={{ backgroundColor: 'var(--midnight)', color: 'white' }}
          >
            Previous
          </button>
          <span className="text-[12px] text-gray-500">
            Page {pageIndex + 1}
          </span>
          <button
            onClick={goNext}
            disabled={!data.has_more}
            className="px-4 py-1.5 rounded text-sm font-semibold disabled:opacity-30 transition-colors"
            style={{ backgroundColor: 'var(--midnight)', color: 'white' }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
