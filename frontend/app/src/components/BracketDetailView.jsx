/**
 * BracketDetailView: Full tournament bracket visualization.
 * Shows all 63 games across 4 regions + Final Four.
 * Horizontal bracket tree layout with connector lines.
 */

const REGION_ACCENT = {
  East: '#00D4FF',
  South: '#FF6B35',
  West: '#F59E0B',
  Midwest: '#22C55E',
}

const REGION_ORDER = ['East', 'South', 'West', 'Midwest']

function TeamLine({ name, seed, isWinner, isUpset, accent }) {
  return (
    <div
      className="flex items-center gap-1 px-1.5"
      style={{
        color: isWinner
          ? (isUpset ? accent : 'var(--text-primary)')
          : 'var(--text-muted)',
        fontWeight: isWinner ? 600 : 400,
        background: isWinner ? 'rgba(255,255,255,0.04)' : 'transparent',
        fontSize: '10px',
        lineHeight: '16px',
        padding: '1px 6px',
      }}
    >
      <span
        className="font-mono shrink-0"
        style={{
          fontSize: '9px',
          width: '14px',
          textAlign: 'right',
          color: isUpset && isWinner ? accent : 'var(--text-muted)',
        }}
      >
        {seed}
      </span>
      <span className="truncate">{name}</span>
      {isWinner && (
        <span className="ml-auto shrink-0" style={{ color: accent, fontSize: '6px' }}>
          {isUpset ? '!!' : '\u25CF'}
        </span>
      )}
    </div>
  )
}

function MatchupBox({ game, accent }) {
  const team0Win = game.winner === game.teams[0]

  return (
    <div
      style={{
        background: game.upset ? `${accent}08` : 'rgba(255,255,255,0.02)',
        border: `1px solid ${game.upset ? accent + '40' : 'var(--border-subtle)'}`,
        borderRadius: '3px',
        width: '120px',
        overflow: 'hidden',
      }}
    >
      <TeamLine
        name={game.teams[0]}
        seed={game.seeds[0]}
        isWinner={team0Win}
        isUpset={game.upset && team0Win}
        accent={accent}
      />
      <div style={{ borderTop: `1px solid ${game.upset ? accent + '20' : 'var(--border-subtle)'}` }} />
      <TeamLine
        name={game.teams[1]}
        seed={game.seeds[1]}
        isWinner={!team0Win}
        isUpset={game.upset && !team0Win}
        accent={accent}
      />
    </div>
  )
}

function ConnectorColumn({ pairs }) {
  return (
    <div className="flex flex-col" style={{ width: '12px' }}>
      {Array.from({ length: pairs }, (_, i) => (
        <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div
            style={{
              flex: 1,
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              borderRight: '1px solid rgba(255,255,255,0.08)',
            }}
          />
          <div
            style={{
              flex: 1,
              borderTop: '1px solid rgba(255,255,255,0.08)',
              borderRight: '1px solid rgba(255,255,255,0.08)',
            }}
          />
        </div>
      ))}
    </div>
  )
}

function RegionBracket({ region, data, accent }) {
  const rounds = ['R64', 'R32', 'S16', 'E8']
  const roundLabels = { R64: 'RD 64', R32: 'RD 32', S16: 'SWEET 16', E8: 'ELITE 8' }
  const connectorCounts = [4, 2, 1]

  const bracketElements = []
  rounds.forEach((r, ri) => {
    bracketElements.push(
      <div
        key={r}
        className="flex flex-col justify-around shrink-0"
        style={{ width: '120px' }}
      >
        {(data[r] || []).map((game, i) => (
          <MatchupBox key={i} game={game} accent={accent} />
        ))}
      </div>
    )
    if (ri < rounds.length - 1) {
      bracketElements.push(
        <ConnectorColumn key={`conn-${ri}`} pairs={connectorCounts[ri]} />
      )
    }
  })

  return (
    <div>
      {/* Region header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="w-1 h-4 rounded-full" style={{ backgroundColor: accent }} />
        <span
          className="text-[11px] font-display tracking-wider"
          style={{ color: accent }}
        >
          {region.toUpperCase()}
        </span>
        <span className="text-[9px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
          CHAMP: {data.champion?.name} ({data.champion?.seed})
        </span>
      </div>

      {/* Round labels */}
      <div className="flex mb-1 overflow-x-auto">
        {rounds.map((r, ri) => (
          <div key={r} style={{ width: '120px' }} className="shrink-0">
            <span className="text-[8px] font-mono block text-center" style={{ color: 'var(--text-muted)' }}>
              {roundLabels[r]}
            </span>
          </div>
        ))}
      </div>

      {/* Bracket tree */}
      <div className="flex overflow-x-auto" style={{ height: '340px' }}>
        {bracketElements}
      </div>
    </div>
  )
}

function F4MatchupBox({ teams, winner, label, isChampionship }) {
  return (
    <div
      style={{
        background: isChampionship ? 'rgba(255,107,53,0.05)' : 'rgba(255,255,255,0.02)',
        border: `1px solid ${isChampionship ? 'var(--border-accent)' : 'var(--border-subtle)'}`,
        borderRadius: isChampionship ? '6px' : '4px',
        width: isChampionship ? '180px' : '160px',
        overflow: 'hidden',
      }}
    >
      <div
        className="text-center py-0.5"
        style={{
          fontSize: isChampionship ? '9px' : '8px',
          fontFamily: 'var(--font-display, inherit)',
          letterSpacing: '0.1em',
          color: isChampionship ? 'var(--orange)' : 'var(--text-muted)',
          background: isChampionship ? 'rgba(255,107,53,0.08)' : 'rgba(255,255,255,0.02)',
        }}
      >
        {label}
      </div>
      {teams.map((team, i) => (
        <div key={team + i}>
          {i > 0 && (
            <div
              style={{
                borderTop: `1px solid ${isChampionship ? 'var(--border-accent)' : 'var(--border-subtle)'}`,
              }}
            />
          )}
          <div
            className="flex items-center gap-1 px-2"
            style={{
              color: winner === team
                ? (isChampionship ? 'var(--orange)' : 'var(--text-primary)')
                : 'var(--text-muted)',
              fontWeight: winner === team ? (isChampionship ? 700 : 600) : 400,
              background: winner === team ? 'rgba(255,255,255,0.04)' : 'transparent',
              fontSize: isChampionship ? '12px' : '11px',
              padding: isChampionship ? '6px 8px' : '4px 8px',
            }}
          >
            <span className="truncate">{team}</span>
            {winner === team && (
              <span
                className="ml-auto shrink-0 font-mono"
                style={{
                  color: 'var(--orange)',
                  fontSize: isChampionship ? '10px' : '8px',
                }}
              >
                {isChampionship ? 'CHAMP' : '\u25CF'}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function FinalFourView({ finalFour }) {
  if (!finalFour) return null

  return (
    <div className="glass rounded-lg p-4">
      <div className="text-center mb-3">
        <span
          className="text-xs tracking-widest"
          style={{ color: 'var(--orange)', fontFamily: 'var(--font-display, inherit)' }}
        >
          FINAL FOUR
        </span>
      </div>

      <div className="flex items-center justify-center gap-4 flex-wrap">
        <F4MatchupBox
          teams={finalFour.semi1.teams}
          winner={finalFour.semi1.winner}
          label="SEMIFINAL 1"
        />
        <F4MatchupBox
          teams={finalFour.championship.teams}
          winner={finalFour.championship.winner}
          label="CHAMPIONSHIP"
          isChampionship
        />
        <F4MatchupBox
          teams={finalFour.semi2.teams}
          winner={finalFour.semi2.winner}
          label="SEMIFINAL 2"
        />
      </div>
    </div>
  )
}

export default function BracketDetailView({ data }) {
  if (!data?.regions) return null

  return (
    <div className="space-y-4">
      {/* 2x2 region grid — East vs South (semi1), West vs Midwest (semi2) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {REGION_ORDER.map((region) => {
          const regionData = data.regions[region]
          if (!regionData) return null
          return (
            <div key={region} className="glass rounded-lg p-3 min-w-0 overflow-hidden">
              <RegionBracket
                region={region}
                data={regionData}
                accent={REGION_ACCENT[region] || 'var(--orange)'}
              />
            </div>
          )
        })}
      </div>

      {/* Final Four + Championship */}
      <FinalFourView finalFour={data.final_four} />
    </div>
  )
}
