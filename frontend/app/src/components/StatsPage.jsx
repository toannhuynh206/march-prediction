/**
 * Statistics dashboard: survival stats, champion odds, upset distribution.
 * Uses React Query for data fetching and Recharts for visualization.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchStats, fetchRegionStats } from '../api/client'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts'

const REGIONS = ['South', 'East', 'West', 'Midwest']
const REGION_COLORS = { South: '#E8611A', East: '#1E3A5F', West: '#D4A843', Midwest: '#2C7A4B' }

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-white rounded-lg shadow-sm p-4 text-center">
      <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{label}</div>
      <div className="text-2xl font-bold" style={{ color: 'var(--midnight)' }}>{value}</div>
      {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function ChampionOddsChart({ data }) {
  if (!data || data.length === 0) return null

  const top15 = data.slice(0, 15)
  return (
    <div className="bg-white rounded-lg shadow-sm p-4">
      <h3 className="text-[13px] font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--midnight)' }}>
        Champion Probability (Top 15)
      </h3>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={top15} layout="vertical" margin={{ left: 100, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} fontSize={10} />
          <YAxis type="category" dataKey="name" fontSize={10} width={95} />
          <Tooltip
            formatter={(v) => `${(v * 100).toFixed(3)}%`}
            labelStyle={{ fontWeight: 'bold' }}
          />
          <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
            {top15.map((entry, i) => (
              <Cell key={i} fill={i < 4 ? 'var(--orange)' : 'var(--midnight)'} opacity={1 - i * 0.04} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function UpsetDistributionChart({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="bg-white rounded-lg shadow-sm p-4">
      <h3 className="text-[13px] font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--midnight)' }}>
        Upset Count Distribution
      </h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
          <XAxis dataKey="upsets" fontSize={10} label={{ value: 'Number of Upsets', position: 'bottom', fontSize: 10 }} />
          <YAxis fontSize={10} tickFormatter={(v) => v.toLocaleString()} />
          <Tooltip
            formatter={(v) => v.toLocaleString()}
            labelFormatter={(l) => `${l} upsets`}
          />
          <Bar dataKey="count" fill="var(--orange)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function RegionPanel({ region }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['region-stats', region],
    queryFn: () => fetchRegionStats(region),
  })

  if (isLoading) return <div className="text-center text-gray-400 text-sm py-4">Loading {region}...</div>
  if (error) return <div className="text-center text-red-500 text-sm py-4">Error: {error.message}</div>

  return (
    <div className="bg-white rounded-lg shadow-sm p-4">
      <h3 className="text-[13px] font-bold uppercase tracking-wider mb-3"
          style={{ color: REGION_COLORS[region], borderLeft: `3px solid ${REGION_COLORS[region]}`, paddingLeft: '8px' }}>
        {region} Region
      </h3>
      <div className="space-y-1">
        {(data.teams || []).map((team) => (
          <div key={team.seed} className="flex items-center text-[11px] gap-2 py-0.5">
            <span className="font-bold text-gray-400 w-5 text-right">{team.seed}</span>
            <span className="flex-1 font-medium" style={{ color: 'var(--midnight)' }}>{team.name}</span>
            {team.survival_rate != null && (
              <span className="text-gray-500 font-mono">{(team.survival_rate * 100).toFixed(1)}%</span>
            )}
          </div>
        ))}
      </div>
      {data.results && data.results.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="text-[10px] font-bold uppercase text-gray-400 mb-1">Results</div>
          {data.results.map((r, i) => (
            <div key={i} className="text-[11px] text-gray-600">
              {r.round}: <span className="font-semibold">{r.winner}</span> def. {r.loser}
              {r.upset && <span className="text-orange-500 font-bold ml-1">UPSET</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function StatsPage() {
  const [selectedRegion, setSelectedRegion] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
  })

  if (isLoading) {
    return <div className="flex items-center justify-center py-20 text-gray-400">Loading statistics...</div>
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error.message}</div>
  }

  const survivalPct = data.total > 0 ? ((data.alive_count / data.total) * 100).toFixed(2) : '0'

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total Brackets" value={data.total?.toLocaleString()} />
        <StatCard label="Alive" value={data.alive_count?.toLocaleString()} sub={`${survivalPct}% survival`} />
        <StatCard label="Games Played" value={data.games_played || 0} sub={`of 63`} />
        <StatCard label="Upsets So Far" value={data.upsets_so_far || 0} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChampionOddsChart data={data.champion_odds} />
        <UpsetDistributionChart data={data.upset_distribution} />
      </div>

      {/* Region selector */}
      <div className="bg-white rounded-lg shadow-sm p-4">
        <h3 className="text-[13px] font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--midnight)' }}>
          Region Details
        </h3>
        <div className="flex gap-2 mb-4">
          {REGIONS.map((r) => (
            <button
              key={r}
              onClick={() => setSelectedRegion(selectedRegion === r ? null : r)}
              className={`px-4 py-1.5 rounded text-sm font-semibold transition-colors ${
                selectedRegion === r ? 'text-white' : 'text-gray-600 bg-gray-100 hover:bg-gray-200'
              }`}
              style={selectedRegion === r ? { backgroundColor: REGION_COLORS[r] } : {}}
            >
              {r}
            </button>
          ))}
        </div>
        {selectedRegion && <RegionPanel region={selectedRegion} />}
      </div>
    </div>
  )
}
