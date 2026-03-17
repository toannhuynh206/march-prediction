/**
 * Portfolio page — financial terminal aesthetic.
 * Displays bracket strategies as stock-like positions with tickers,
 * survival rates as "returns", weight share as market cap, and
 * champion distributions per strategy.
 */

import { useQuery } from '@tanstack/react-query'
import { fetchPortfolio } from '../api/client'
import { getTeamColor } from '../constants/teamColors'

const RISK_COLORS = {
  low: '#22C55E',
  medium: '#3B82F6',
  high: '#F97316',
  'very-high': '#EF4444',
}

const RISK_LABELS = {
  low: 'LOW',
  medium: 'MED',
  high: 'HIGH',
  'very-high': 'V-HI',
}

function TickerHeader({ strategy }) {
  const riskColor = RISK_COLORS[strategy.risk_level] || '#64748B'
  const survivalReturn = strategy.survival_rate - 1
  const isPositive = survivalReturn >= 0
  const returnStr = `${isPositive ? '+' : ''}${(survivalReturn * 100).toFixed(2)}%`

  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        <div className="flex items-center gap-3">
          <span
            className="font-mono text-2xl font-black tracking-wider"
            style={{ color: 'var(--text-primary)' }}
          >
            {strategy.ticker}
          </span>
          <span
            className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-sm"
            style={{
              color: riskColor,
              border: `1px solid ${riskColor}40`,
              background: `${riskColor}10`,
            }}
          >
            {RISK_LABELS[strategy.risk_level] || 'UNK'}
          </span>
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
          {strategy.display_name}
        </div>
      </div>
      <div className="text-right">
        <div
          className="font-mono text-xl font-bold"
          style={{ color: isPositive ? 'var(--green-alive)' : 'var(--red-dead)' }}
        >
          {returnStr}
        </div>
        <div className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          SURVIVAL
        </div>
      </div>
    </div>
  )
}

function MetricRow({ label, value, sub }) {
  return (
    <div className="flex justify-between items-baseline py-1.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <span className="text-[11px] font-mono uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
        {label}
      </span>
      <div className="text-right">
        <span className="text-sm font-mono font-semibold" style={{ color: 'var(--text-primary)' }}>
          {value}
        </span>
        {sub && (
          <span className="text-[10px] font-mono ml-1.5" style={{ color: 'var(--text-muted)' }}>
            {sub}
          </span>
        )}
      </div>
    </div>
  )
}

function ChampionBar({ champions, strategyColor }) {
  if (!champions || champions.length === 0) return null

  return (
    <div className="mt-3">
      <div className="text-[10px] font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
        TOP PICKS
      </div>
      <div className="space-y-1.5">
        {champions.map((c) => {
          const pct = (c.probability * 100).toFixed(1)
          const teamColor = getTeamColor(c.name)
          return (
            <div key={c.name} className="flex items-center gap-2">
              <div
                className="w-1.5 h-4 rounded-sm flex-shrink-0"
                style={{ background: teamColor }}
              />
              <span className="text-xs flex-1 truncate" style={{ color: 'var(--text-secondary)' }}>
                <span className="font-mono text-[10px] mr-1" style={{ color: 'var(--text-muted)' }}>
                  ({c.seed})
                </span>
                {c.name}
              </span>
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border-subtle)' }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(c.probability * 100 / 0.3 * 100, 100)}%`,
                      background: teamColor,
                    }}
                  />
                </div>
                <span className="font-mono text-[11px] w-12 text-right" style={{ color: 'var(--text-primary)' }}>
                  {pct}%
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StrategyCard({ strategy }) {
  const riskColor = RISK_COLORS[strategy.risk_level] || '#64748B'

  return (
    <div
      className="glass rounded-xl p-5 relative overflow-hidden group transition-all duration-300 hover:translate-y-[-2px]"
      style={{
        border: '1px solid var(--border-subtle)',
        boxShadow: `0 0 0 0 ${riskColor}00`,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = `0 4px 30px ${riskColor}15` }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = `0 0 0 0 ${riskColor}00` }}
    >
      {/* Top accent line */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{ background: `linear-gradient(90deg, transparent, ${riskColor}, transparent)` }}
      />

      <TickerHeader strategy={strategy} />

      <div className="text-[11px] mb-4 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
        {strategy.description}
      </div>

      <MetricRow
        label="Positions"
        value={strategy.alive_count.toLocaleString()}
        sub={`/ ${strategy.total_count.toLocaleString()}`}
      />
      <MetricRow
        label="Weight Share"
        value={`${(strategy.weight_share * 100).toFixed(1)}%`}
      />
      <MetricRow
        label="Allocation"
        value={`${(strategy.allocation_pct * 100).toFixed(0)}%`}
      />
      <MetricRow
        label="Avg Weight"
        value={strategy.avg_weight.toFixed(4)}
      />
      <MetricRow
        label="Avg Upsets"
        value={strategy.avg_upsets}
        sub={`${strategy.min_upsets}–${strategy.max_upsets}`}
      />
      <MetricRow
        label="ESS"
        value={strategy.ess.toLocaleString()}
        sub={`${strategy.ess_pct}%`}
      />
      <MetricRow
        label="Temperature"
        value={`${strategy.base_temp}`}
        sub={strategy.base_temp !== strategy.upset_temp ? `/ ${strategy.upset_temp} upset` : ''}
      />

      <ChampionBar champions={strategy.top_champions} strategyColor={riskColor} />
    </div>
  )
}

function AllocationBar({ strategies }) {
  return (
    <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 className="font-display text-lg tracking-wider mb-4" style={{ color: 'var(--text-primary)' }}>
        PORTFOLIO ALLOCATION
      </h3>

      {/* Stacked bar */}
      <div className="flex h-8 rounded-lg overflow-hidden mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
        {strategies.map((s) => {
          const color = RISK_COLORS[s.risk_level] || '#64748B'
          const widthPct = s.weight_share * 100
          return (
            <div
              key={s.name}
              className="relative group/seg flex items-center justify-center"
              style={{
                width: `${widthPct}%`,
                background: color,
                minWidth: widthPct > 3 ? undefined : '12px',
              }}
              title={`${s.ticker}: ${widthPct.toFixed(1)}%`}
            >
              {widthPct > 8 && (
                <span className="text-[10px] font-mono font-bold text-white/90">
                  {s.ticker}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-5 gap-y-1">
        {strategies.map((s) => {
          const color = RISK_COLORS[s.risk_level] || '#64748B'
          return (
            <div key={s.name} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
              <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                {s.ticker}
              </span>
              <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                {(s.weight_share * 100).toFixed(1)}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PortfolioSummary({ data }) {
  const totalAlive = data.alive_brackets
  const totalBrackets = data.total_brackets
  const survivalPct = totalBrackets > 0 ? ((totalAlive / totalBrackets) * 100).toFixed(2) : '0'
  const totalESS = data.strategies.reduce((sum, s) => sum + s.ess, 0)

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        className="glass rounded-xl p-5 text-center"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: 'var(--text-muted)' }}>
          TOTAL AUM
        </div>
        <div className="font-display text-3xl" style={{ color: 'var(--text-primary)' }}>
          {totalBrackets.toLocaleString()}
        </div>
        <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          brackets
        </div>
      </div>

      <div
        className="glass rounded-xl p-5 text-center"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: 'var(--text-muted)' }}>
          ACTIVE POSITIONS
        </div>
        <div className="font-display text-3xl" style={{ color: 'var(--green-alive)' }}>
          {totalAlive.toLocaleString()}
        </div>
        <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          {survivalPct}% alive
        </div>
      </div>

      <div
        className="glass rounded-xl p-5 text-center"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: 'var(--text-muted)' }}>
          STRATEGIES
        </div>
        <div className="font-display text-3xl" style={{ color: 'var(--cyan)' }}>
          {data.strategies.length}
        </div>
        <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          active profiles
        </div>
      </div>

      <div
        className="glass rounded-xl p-5 text-center"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: 'var(--text-muted)' }}>
          PORTFOLIO ESS
        </div>
        <div className="font-display text-3xl" style={{ color: 'var(--orange)' }}>
          {totalESS.toLocaleString()}
        </div>
        <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          effective samples
        </div>
      </div>
    </div>
  )
}

export default function PortfolioPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
  })

  if (isLoading) {
    return (
      <div className="glass rounded-xl p-8 flex flex-col items-center gap-4 py-16">
        <div
          className="w-12 h-12 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--orange)', borderTopColor: 'transparent' }}
        />
        <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
          LOADING PORTFOLIO...
        </span>
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

  return (
    <div className="space-y-5">
      {/* Ticker tape header */}
      <div
        className="glass rounded-xl overflow-hidden"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <div className="px-5 py-3 flex items-center gap-4 overflow-x-auto" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <span className="text-[10px] font-mono uppercase tracking-[0.3em] flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
            MARCH MADNESS PORTFOLIO
          </span>
          <div className="h-3 w-px flex-shrink-0" style={{ background: 'var(--border-subtle)' }} />
          {data.strategies.map((s) => {
            const riskColor = RISK_COLORS[s.risk_level] || '#64748B'
            const survRet = s.survival_rate - 1
            const isPos = survRet >= 0
            return (
              <div key={s.name} className="flex items-center gap-2 flex-shrink-0">
                <span className="font-mono text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
                  {s.ticker}
                </span>
                <span
                  className="font-mono text-[11px] font-semibold"
                  style={{ color: isPos ? 'var(--green-alive)' : 'var(--red-dead)' }}
                >
                  {isPos ? '+' : ''}{(survRet * 100).toFixed(1)}%
                </span>
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: riskColor }} />
              </div>
            )
          })}
        </div>
      </div>

      <PortfolioSummary data={data} />
      <AllocationBar strategies={data.strategies} />

      {/* Strategy cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.strategies.map((s) => (
          <StrategyCard key={s.name} strategy={s} />
        ))}
      </div>
    </div>
  )
}
