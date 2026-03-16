/**
 * Statistics dashboard — dark broadcast aesthetic with glowing stat cards.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchStats, fetchRegionStats } from '../api/client'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie,
} from 'recharts'
import { getTeamColor, REST_SLICE_COLOR } from '../constants/teamColors'

const REGIONS = ['South', 'East', 'West', 'Midwest']
const REGION_ACCENT = { South: '#FF6B35', East: '#00D4FF', West: '#F59E0B', Midwest: '#22C55E' }

function StatCard({ label, value, sub, accent }) {
  const color = accent || 'var(--text-primary)'
  return (
    <div
      className="glass rounded-xl p-5 text-center relative overflow-hidden group transition-all duration-300"
      style={{ border: '1px solid var(--border-subtle)' }}
    >
      {/* Background glow */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{ background: `radial-gradient(circle at 50% 100%, ${accent || 'var(--orange)'}10, transparent 70%)` }}
      />
      <div className="relative z-10">
        <div
          className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2"
          style={{ color: 'var(--text-muted)' }}
        >
          {label}
        </div>
        <div className="font-display text-4xl" style={{ color }}>
          {value}
        </div>
        {sub && (
          <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  )
}

function ChampionOddsChart({ data }) {
  if (!data || data.length === 0) return null

  const top15 = data.slice(0, 15)
  return (
    <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 className="font-display text-lg tracking-wider mb-4" style={{ color: 'var(--orange)' }}>
        CHAMPION PROBABILITY
      </h3>
      <ResponsiveContainer width="100%" height={340}>
        <BarChart data={top15} layout="vertical" margin={{ left: 100, right: 20, top: 5, bottom: 5 }}>
          <XAxis
            type="number"
            tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
            fontSize={10}
            stroke="var(--text-muted)"
            axisLine={{ stroke: 'var(--border-subtle)' }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            fontSize={11}
            width={95}
            stroke="var(--text-muted)"
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(v) => `${(v * 100).toFixed(3)}%`}
            contentStyle={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              color: 'var(--text-primary)',
            }}
            labelStyle={{ fontWeight: 'bold', color: 'var(--text-primary)' }}
          />
          <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
            {top15.map((entry, i) => (
              <Cell key={i} fill={i < 4 ? 'var(--orange)' : '#334155'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ChampionPieChart({ data }) {
  if (!data || data.length === 0) return null

  const top6 = data.slice(0, 6)
  const restProb = data.slice(6).reduce((sum, d) => sum + d.probability, 0)
  const pieData = [
    ...top6.map((d) => ({ name: d.name, value: d.probability })),
    ...(restProb > 0 ? [{ name: 'Rest', value: restProb }] : []),
  ]
  const colors = [
    ...top6.map((d) => getTeamColor(d.name)),
    REST_SLICE_COLOR,
  ]

  const renderLabel = ({ name, value, cx, x, y }) => {
    const anchor = x > cx ? 'start' : 'end'
    return (
      <text x={x} y={y} textAnchor={anchor} fill="var(--text-secondary)" fontSize={11} fontFamily="'JetBrains Mono', monospace">
        {name} {(value * 100).toFixed(1)}%
      </text>
    )
  }

  return (
    <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 className="font-display text-lg tracking-wider mb-4" style={{ color: 'var(--orange)' }}>
        CHAMPION DISTRIBUTION
      </h3>
      <ResponsiveContainer width="100%" height={340}>
        <PieChart>
          <Pie
            data={pieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={120}
            innerRadius={55}
            strokeWidth={2}
            stroke="var(--bg-deep)"
            label={renderLabel}
            labelLine={{ stroke: 'var(--text-muted)', strokeWidth: 1 }}
          >
            {pieData.map((_, i) => (
              <Cell key={i} fill={colors[i]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(v) => `${(v * 100).toFixed(2)}%`}
            contentStyle={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              color: 'var(--text-primary)',
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function UpsetDistributionChart({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 className="font-display text-lg tracking-wider mb-4" style={{ color: 'var(--cyan)' }}>
        UPSET DISTRIBUTION
      </h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ left: 10, right: 10, top: 5, bottom: 20 }}>
          <XAxis
            dataKey="upsets"
            fontSize={10}
            stroke="var(--text-muted)"
            axisLine={{ stroke: 'var(--border-subtle)' }}
            tickLine={false}
            label={{ value: 'Number of Upsets', position: 'bottom', fontSize: 10, fill: 'var(--text-muted)', offset: 5 }}
          />
          <YAxis
            fontSize={10}
            stroke="var(--text-muted)"
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => v.toLocaleString()}
          />
          <Tooltip
            formatter={(v) => v.toLocaleString()}
            labelFormatter={(l) => `${l} upsets`}
            contentStyle={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              color: 'var(--text-primary)',
            }}
          />
          <Bar dataKey="count" fill="var(--cyan)" radius={[4, 4, 0, 0]} opacity={0.8} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function RegionPanel({ region }) {
  const accent = REGION_ACCENT[region]
  const { data, isLoading, error } = useQuery({
    queryKey: ['region-stats', region],
    queryFn: () => fetchRegionStats(region),
  })

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>Loading {region}...</span>
      </div>
    )
  }
  if (error) {
    return <div className="text-center py-4 text-sm" style={{ color: 'var(--red-dead)' }}>Error: {error.message}</div>
  }

  return (
    <div className="animate-fade-up">
      <div className="space-y-1">
        {(data.teams || []).map((team) => (
          <div
            key={team.seed}
            className="flex items-center text-[12px] gap-3 py-1.5 px-3 rounded-lg transition-colors"
            style={{ ':hover': { background: 'rgba(255,255,255,0.02)' } }}
          >
            <span
              className="font-mono font-bold w-6 text-center text-[11px]"
              style={{ color: accent, opacity: 0.7 }}
            >
              {team.seed}
            </span>
            <span className="flex-1 font-medium" style={{ color: 'var(--text-primary)' }}>
              {team.name}
            </span>
            {team.survival_rate != null && (
              <span className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                {(team.survival_rate * 100).toFixed(1)}%
              </span>
            )}
          </div>
        ))}
      </div>
      {data.results && data.results.length > 0 && (
        <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <div className="text-[10px] font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
            Results
          </div>
          {data.results.map((r, i) => (
            <div key={i} className="text-[12px] py-0.5" style={{ color: 'var(--text-secondary)' }}>
              <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{r.round}</span>
              {' '}
              <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{r.winner}</span>
              {' def. '}{r.loser}
              {r.upset && (
                <span
                  className="ml-2 font-mono text-[9px] font-bold px-1.5 py-0.5 rounded"
                  style={{ color: 'var(--orange)', background: 'var(--orange-glow)' }}
                >
                  UPSET
                </span>
              )}
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
    return (
      <div className="glass rounded-xl p-8 flex flex-col items-center gap-4 py-16">
        <div className="w-12 h-12 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--orange)', borderTopColor: 'transparent' }} />
        <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>LOADING STATISTICS...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass rounded-xl p-6 glow-orange">
        <p className="font-semibold" style={{ color: 'var(--orange)' }}>Error: {error.message}</p>
      </div>
    )
  }

  const survivalPct = data.total > 0 ? ((data.alive_count / data.total) * 100).toFixed(2) : '0'

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Brackets" value={data.total?.toLocaleString()} accent="var(--text-primary)" />
        <StatCard label="Alive" value={data.alive_count?.toLocaleString()} sub={`${survivalPct}% survival`} accent="var(--green-alive)" />
        <StatCard label="Games Played" value={data.games_played || 0} sub="of 63" accent="var(--cyan)" />
        <StatCard label="Upsets" value={data.upsets_so_far || 0} accent="var(--orange)" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChampionPieChart data={data.champion_odds} />
        <ChampionOddsChart data={data.champion_odds} />
      </div>
      <div className="grid grid-cols-1 gap-4">
        <UpsetDistributionChart data={data.upset_distribution} />
      </div>

      {/* Region selector */}
      <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border-subtle)' }}>
        <h3 className="font-display text-lg tracking-wider mb-4" style={{ color: 'var(--text-primary)' }}>
          REGION DETAILS
        </h3>
        <div className="flex gap-2 mb-5">
          {REGIONS.map((r) => {
            const isActive = selectedRegion === r
            return (
              <button
                key={r}
                onClick={() => setSelectedRegion(isActive ? null : r)}
                className="px-5 py-2 rounded-lg font-mono text-xs font-semibold tracking-wider transition-all duration-200"
                style={{
                  color: isActive ? 'white' : REGION_ACCENT[r],
                  backgroundColor: isActive ? REGION_ACCENT[r] : 'transparent',
                  border: `1px solid ${isActive ? REGION_ACCENT[r] : REGION_ACCENT[r] + '40'}`,
                  boxShadow: isActive ? `0 0 20px ${REGION_ACCENT[r]}20` : 'none',
                }}
              >
                {r.toUpperCase()}
              </button>
            )
          })}
        </div>
        {selectedRegion && <RegionPanel region={selectedRegion} />}
      </div>
    </div>
  )
}
