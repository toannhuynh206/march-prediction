/**
 * BracketDetailView: Full tournament bracket visualization.
 * Shows all 63 games across 4 regions + Final Four.
 * Horizontal bracket tree layout with connector lines.
 *
 * Accepts optional `gameResults` prop (array from GET /api/game-results)
 * to overlay correct/busted indicators on each game.
 */

const REGION_ACCENT = {
  East: '#00D4FF',
  South: '#FF6B35',
  West: '#F59E0B',
  Midwest: '#22C55E',
}

const REGION_ORDER = ['East', 'South', 'West', 'Midwest']

const ROUND_OFFSET = { R64: 0, R32: 8, S16: 12, E8: 14 }

function buildResultsLookup(gameResults) {
  if (!gameResults?.length) return null
  const regions = {}
  const f4 = {}
  for (const r of gameResults) {
    if (r.round === 'F4') {
      f4[r.game_number] = r
    } else if (r.round === 'Final') {
      f4.championship = r
    } else {
      const absIdx = (ROUND_OFFSET[r.round] ?? 0) + r.game_number
      if (!regions[r.region]) regions[r.region] = {}
      regions[r.region][absIdx] = r
    }
  }
  return { regions, f4 }
}

function TeamLine({ name, seed, isWinner, isUpset, accent, resultStatus }) {
  // resultStatus: null | 'correct' | 'wrong-pick' | 'actual-winner'
  const isCorrectWinner = resultStatus === 'correct'
  const isWrongPick = resultStatus === 'wrong-pick'
  const isActualWinner = resultStatus === 'actual-winner'

  return (
    <div
      className="flex items-center gap-1 px-1.5"
      style={{
        color: isWrongPick
          ? 'var(--red-dead, #ef4444)'
          : isCorrectWinner
            ? 'var(--green-alive, #22c55e)'
            : isActualWinner
              ? 'var(--green-alive, #22c55e)'
              : isWinner
                ? (isUpset ? accent : 'var(--text-primary)')
                : 'var(--text-muted)',
        fontWeight: isWinner || isActualWinner ? 600 : 400,
        background: isWrongPick
          ? 'rgba(239,68,68,0.08)'
          : isCorrectWinner
            ? 'rgba(34,197,94,0.06)'
            : isActualWinner
              ? 'rgba(34,197,94,0.04)'
              : isWinner ? 'rgba(255,255,255,0.04)' : 'transparent',
        textDecoration: isWrongPick ? 'line-through' : 'none',
        opacity: isWrongPick ? 0.7 : 1,
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
          color: isWrongPick
            ? 'var(--red-dead, #ef4444)'
            : isCorrectWinner
              ? 'var(--green-alive, #22c55e)'
              : isActualWinner
                ? 'var(--green-alive, #22c55e)'
                : isUpset && isWinner ? accent : 'var(--text-muted)',
        }}
      >
        {seed}
      </span>
      <span className="truncate">{name}</span>
      {isCorrectWinner && (
        <span className="ml-auto shrink-0 font-mono" style={{ color: 'var(--green-alive, #22c55e)', fontSize: '8px' }}>
          &#10003;
        </span>
      )}
      {isWrongPick && (
        <span className="ml-auto shrink-0 font-mono" style={{ color: 'var(--red-dead, #ef4444)', fontSize: '8px' }}>
          &#10007;
        </span>
      )}
      {isActualWinner && (
        <span className="ml-auto shrink-0 font-mono" style={{ color: 'var(--green-alive, #22c55e)', fontSize: '7px', letterSpacing: '0.05em' }}>
          WON
        </span>
      )}
      {!resultStatus && isWinner && (
        <span className="ml-auto shrink-0" style={{ color: accent, fontSize: '6px' }}>
          {isUpset ? '!!' : '\u25CF'}
        </span>
      )}
    </div>
  )
}

function MatchupBox({ game, accent, actualResult }) {
  const team0Win = game.winner === game.teams[0]
  const hasResult = !!actualResult
  const isCorrect = hasResult && game.winner === actualResult.winner_name
  const isBusted = hasResult && !isCorrect

  // Determine result status for each team line
  let team0Status = null
  let team1Status = null
  if (hasResult) {
    if (isCorrect) {
      team0Status = team0Win ? 'correct' : null
      team1Status = !team0Win ? 'correct' : null
    } else {
      // Bracket's pick was wrong
      if (team0Win) {
        team0Status = 'wrong-pick'
        team1Status = actualResult.winner_name === game.teams[1] ? 'actual-winner' : null
      } else {
        team1Status = 'wrong-pick'
        team0Status = actualResult.winner_name === game.teams[0] ? 'actual-winner' : null
      }
    }
  }

  return (
    <div
      style={{
        background: isBusted
          ? 'rgba(239,68,68,0.06)'
          : isCorrect
            ? 'rgba(34,197,94,0.04)'
            : game.upset ? `${accent}08` : 'rgba(255,255,255,0.02)',
        border: `1px solid ${
          isBusted
            ? 'rgba(239,68,68,0.45)'
            : isCorrect
              ? 'rgba(34,197,94,0.3)'
              : game.upset ? accent + '40' : 'var(--border-subtle)'
        }`,
        borderLeft: isBusted
          ? '3px solid var(--red-dead, #ef4444)'
          : isCorrect
            ? '3px solid var(--green-alive, #22c55e)'
            : undefined,
        borderRadius: '3px',
        width: '120px',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      <TeamLine
        name={game.teams[0]}
        seed={game.seeds[0]}
        isWinner={team0Win}
        isUpset={game.upset && team0Win}
        accent={accent}
        resultStatus={team0Status}
      />
      <div style={{ borderTop: `1px solid ${
        isBusted
          ? 'rgba(239,68,68,0.2)'
          : isCorrect
            ? 'rgba(34,197,94,0.15)'
            : game.upset ? accent + '20' : 'var(--border-subtle)'
      }` }} />
      <TeamLine
        name={game.teams[1]}
        seed={game.seeds[1]}
        isWinner={!team0Win}
        isUpset={game.upset && !team0Win}
        accent={accent}
        resultStatus={team1Status}
      />
      {isBusted && (
        <div
          className="text-center py-0.5"
          style={{
            background: 'rgba(239,68,68,0.12)',
            borderTop: '1px solid rgba(239,68,68,0.2)',
            fontSize: '7px',
            fontFamily: 'var(--font-mono, monospace)',
            fontWeight: 700,
            letterSpacing: '0.15em',
            color: 'var(--red-dead, #ef4444)',
          }}
        >
          BUST
        </div>
      )}
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

function RegionBracket({ region, data, accent, regionResults }) {
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
          <MatchupBox
            key={i}
            game={game}
            accent={accent}
            actualResult={regionResults?.[game.game]}
          />
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
        {rounds.map((r) => (
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

function F4MatchupBox({ teams, winner, label, isChampionship, actualResult }) {
  const hasResult = !!actualResult
  const isCorrect = hasResult && winner === actualResult.winner_name
  const isBusted = hasResult && !isCorrect

  return (
    <div
      style={{
        background: isBusted
          ? 'rgba(239,68,68,0.06)'
          : isCorrect
            ? 'rgba(34,197,94,0.04)'
            : isChampionship ? 'rgba(255,107,53,0.05)' : 'rgba(255,255,255,0.02)',
        border: `1px solid ${
          isBusted
            ? 'rgba(239,68,68,0.45)'
            : isCorrect
              ? 'rgba(34,197,94,0.3)'
              : isChampionship ? 'var(--border-accent)' : 'var(--border-subtle)'
        }`,
        borderLeft: isBusted
          ? '3px solid var(--red-dead, #ef4444)'
          : isCorrect
            ? '3px solid var(--green-alive, #22c55e)'
            : undefined,
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
          color: isBusted
            ? 'var(--red-dead, #ef4444)'
            : isCorrect
              ? 'var(--green-alive, #22c55e)'
              : isChampionship ? 'var(--orange)' : 'var(--text-muted)',
          background: isBusted
            ? 'rgba(239,68,68,0.08)'
            : isCorrect
              ? 'rgba(34,197,94,0.06)'
              : isChampionship ? 'rgba(255,107,53,0.08)' : 'rgba(255,255,255,0.02)',
        }}
      >
        {isBusted ? `${label} \u2014 BUST` : isCorrect ? `${label} \u2713` : label}
      </div>
      {teams.map((team, i) => {
        const isBracketPick = team === winner
        const isActualWinner = hasResult && team === actualResult.winner_name
        const isWrongPick = isBracketPick && isBusted
        const isCorrectPick = isBracketPick && isCorrect

        return (
          <div key={team + i}>
            {i > 0 && (
              <div
                style={{
                  borderTop: `1px solid ${
                    isBusted
                      ? 'rgba(239,68,68,0.2)'
                      : isCorrect
                        ? 'rgba(34,197,94,0.15)'
                        : isChampionship ? 'var(--border-accent)' : 'var(--border-subtle)'
                  }`,
                }}
              />
            )}
            <div
              className="flex items-center gap-1 px-2"
              style={{
                color: isWrongPick
                  ? 'var(--red-dead, #ef4444)'
                  : isCorrectPick
                    ? 'var(--green-alive, #22c55e)'
                    : isActualWinner && isBusted
                      ? 'var(--green-alive, #22c55e)'
                      : winner === team
                        ? (isChampionship ? 'var(--orange)' : 'var(--text-primary)')
                        : 'var(--text-muted)',
                fontWeight: isWrongPick ? 600 : winner === team || isActualWinner ? (isChampionship ? 700 : 600) : 400,
                background: isWrongPick
                  ? 'rgba(239,68,68,0.06)'
                  : isCorrectPick || isActualWinner
                    ? 'rgba(34,197,94,0.04)'
                    : winner === team ? 'rgba(255,255,255,0.04)' : 'transparent',
                textDecoration: isWrongPick ? 'line-through' : 'none',
                opacity: isWrongPick ? 0.7 : 1,
                fontSize: isChampionship ? '12px' : '11px',
                padding: isChampionship ? '6px 8px' : '4px 8px',
              }}
            >
              <span className="truncate">{team}</span>
              {isCorrectPick && (
                <span
                  className="ml-auto shrink-0 font-mono"
                  style={{ color: 'var(--green-alive, #22c55e)', fontSize: isChampionship ? '10px' : '8px' }}
                >
                  {isChampionship ? 'CHAMP \u2713' : '\u2713'}
                </span>
              )}
              {isWrongPick && (
                <span
                  className="ml-auto shrink-0 font-mono"
                  style={{ color: 'var(--red-dead, #ef4444)', fontSize: isChampionship ? '10px' : '8px' }}
                >
                  &#10007;
                </span>
              )}
              {isActualWinner && isBusted && (
                <span
                  className="ml-auto shrink-0 font-mono"
                  style={{ color: 'var(--green-alive, #22c55e)', fontSize: isChampionship ? '9px' : '7px', letterSpacing: '0.05em' }}
                >
                  WON
                </span>
              )}
              {!hasResult && winner === team && (
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
        )
      })}
    </div>
  )
}

function FinalFourView({ finalFour, f4Results }) {
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
          actualResult={f4Results?.[0]}
        />
        <F4MatchupBox
          teams={finalFour.championship.teams}
          winner={finalFour.championship.winner}
          label="CHAMPIONSHIP"
          isChampionship
          actualResult={f4Results?.championship}
        />
        <F4MatchupBox
          teams={finalFour.semi2.teams}
          winner={finalFour.semi2.winner}
          label="SEMIFINAL 2"
          actualResult={f4Results?.[1]}
        />
      </div>
    </div>
  )
}

export default function BracketDetailView({ data, gameResults }) {
  if (!data?.regions) return null

  const resultsLookup = gameResults?.length ? buildResultsLookup(gameResults) : null

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
                regionResults={resultsLookup?.regions?.[region]}
              />
            </div>
          )
        })}
      </div>

      {/* Final Four + Championship */}
      <FinalFourView finalFour={data.final_four} f4Results={resultsLookup?.f4} />
    </div>
  )
}
