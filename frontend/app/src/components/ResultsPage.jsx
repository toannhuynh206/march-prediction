/**
 * 2026 Tournament Results Page — portfolio showcase.
 */

export default function ResultsPage() {
  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="glass rounded-xl p-8 text-center">
        <div className="font-mono text-[10px] tracking-[0.3em] uppercase mb-2" style={{ color: 'var(--text-muted)' }}>
          2026 NCAA Tournament
        </div>
        <div className="text-7xl sm:text-8xl font-bold mb-2" style={{ color: 'var(--orange)' }}>
          47<span style={{ color: 'var(--text-muted)' }}>/63</span>
        </div>
        <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Games Predicted Correctly
        </div>
        <div className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          2 brackets survived through 47 games out of 206,000,000 generated
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { val: '206M', label: 'BRACKETS GENERATED', color: 'var(--orange)' },
          { val: '74.6%', label: 'GAME ACCURACY', color: 'var(--green-alive)' },
          { val: '12', label: 'UPSETS PREDICTED', color: 'var(--orange)' },
          { val: '2.4M×', label: 'BETTER THAN RANDOM', color: 'var(--green-alive)' },
        ].map((s) => (
          <div key={s.label} className="glass rounded-xl p-4 text-center">
            <div className="text-2xl font-bold" style={{ color: s.color }}>{s.val}</div>
            <div className="text-[9px] font-mono tracking-wider mt-1" style={{ color: 'var(--text-muted)' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Survival Timeline */}
      <div className="glass rounded-xl p-6">
        <div className="text-[10px] font-mono tracking-[0.3em] uppercase mb-4" style={{ color: 'var(--orange)' }}>
          Survival Timeline
        </div>
        <div className="space-y-4">
          {[
            { round: 'PRE-TOURNAMENT', detail: '206,000,000 brackets generated', sub: 'March 19, 2026 — SHA-256 committed to GitHub before tipoff', alive: true },
            { round: 'ROUND OF 64 (32 games)', detail: '3,515 brackets alive (0.0017%)', sub: '8 upsets predicted — TCU, Saint Louis, VCU, Iowa, High Point, Texas, Texas A&M', alive: true },
            { round: 'R32 DAY 1 (40 games)', detail: '56 brackets alive', sub: 'Texas upset Gonzaga — cinderella profiles had it covered', alive: true },
            { round: 'IOWA UPSETS FLORIDA (43 games)', detail: '2 brackets alive', sub: '9-seed Iowa over 1-seed Florida — only 5.4% of alive brackets had this', alive: false, warning: true },
            { round: 'R32 COMPLETE (47 games)', detail: '2 brackets still perfect', sub: 'Survived UConn, Arizona, Alabama, Tennessee results', alive: true },
            { round: 'SWEET 16', detail: 'Both brackets eliminated', sub: '47 consecutive correct — further than any ESPN bracket in history', alive: false, dead: true },
          ].map((item, i) => (
            <div key={i} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div
                  className="w-3 h-3 rounded-full border-2 flex-shrink-0"
                  style={{
                    borderColor: item.dead ? 'var(--red-dead)' : item.warning ? 'var(--orange)' : 'var(--green-alive)',
                    backgroundColor: item.dead ? 'rgba(239,68,68,0.2)' : item.alive ? 'rgba(34,197,94,0.2)' : 'transparent',
                  }}
                />
                {i < 5 && <div className="w-[2px] flex-1 mt-1" style={{ background: 'rgba(255,107,53,0.15)' }} />}
              </div>
              <div className="pb-2">
                <div className="text-xs font-bold" style={{ color: 'var(--orange)' }}>{item.round}</div>
                <div className="text-sm mt-1" style={{ color: 'var(--text-primary)' }}>{item.detail}</div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{item.sub}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* The Last Two */}
      <div className="glass rounded-xl p-6">
        <div className="text-[10px] font-mono tracking-[0.3em] uppercase mb-4" style={{ color: 'var(--orange)' }}>
          The Last Two Standing
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="rounded-lg p-4" style={{ background: 'rgba(255,107,53,0.04)', border: '1px solid rgba(255,107,53,0.12)' }}>
            <div className="text-[10px] font-mono" style={{ color: 'var(--orange)' }}>BRACKET #55,629,552 — CHALK</div>
            <div className="text-xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>Champion: Houston</div>
            <div className="text-xs mt-2 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
              E8: Duke, Houston, Arizona, Iowa State<br/>
              F4: Houston over Duke, Arizona over Iowa State<br/>
              Final: Houston over Arizona
            </div>
          </div>
          <div className="rounded-lg p-4" style={{ background: 'rgba(255,107,53,0.04)', border: '1px solid rgba(255,107,53,0.12)' }}>
            <div className="text-[10px] font-mono" style={{ color: 'var(--orange)' }}>BRACKET #88,053,121 — STANDARD</div>
            <div className="text-xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>Champion: Michigan</div>
            <div className="text-xs mt-2 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
              E8: Michigan State, Illinois, Arizona, Michigan<br/>
              F4: MSU over Illinois, Michigan over Arizona<br/>
              Final: Michigan over Michigan State
            </div>
          </div>
        </div>
      </div>

      {/* Odds Comparison */}
      <div className="glass rounded-xl p-6">
        <div className="text-[10px] font-mono tracking-[0.3em] uppercase mb-4" style={{ color: 'var(--orange)' }}>
          The Odds
        </div>
        <div className="space-y-3">
          {[
            { label: 'Our model: Perfect R64', odds: '1 in 58,605', ours: true },
            { label: 'Struck by lightning (lifetime)', odds: '1 in 1,222,000' },
            { label: 'Our model: Perfect through R32', odds: '1 in 12,117,647', ours: true },
            { label: 'Winning Powerball', odds: '1 in 292,201,338' },
            { label: 'Perfect R64 (random)', odds: '1 in 4,294,967,296' },
            { label: 'Perfect bracket (expert)', odds: '1 in 120,000,000,000' },
            { label: 'Perfect R32 (random)', odds: '1 in 281,474,976,710,656' },
            { label: 'Perfect bracket (random)', odds: '1 in 9,223,372,036,854,775,808' },
          ].map((item) => (
            <div key={item.label} className="flex justify-between items-center py-1" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
              <span className="text-xs" style={{ color: item.ours ? 'var(--green-alive)' : 'var(--text-muted)' }}>
                {item.label}
              </span>
              <span className="text-xs font-mono" style={{ color: item.ours ? 'var(--green-alive)' : 'var(--text-secondary)' }}>
                {item.odds}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* What Went Right / What to Improve */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="glass rounded-xl p-6">
          <div className="text-[10px] font-mono tracking-[0.3em] uppercase mb-3" style={{ color: 'var(--green-alive)' }}>
            What Went Right
          </div>
          <ul className="space-y-2 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            <li><strong style={{ color: 'var(--text-primary)' }}>Portfolio strategy:</strong> 5 temperature profiles gave upset coverage through 12 upsets</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Importance sampling:</strong> 0.00007% of bracket space, 2.4M times better than random</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>4-layer probability blend:</strong> Vegas + stats + matchup + factors with spread-adaptive weights</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>12 upsets predicted:</strong> Including VCU from 19 down, High Point by 1 point, Texas Cinderella run</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Provable generation:</strong> SHA-256 on GitHub before tipoff, immutable bracket table</li>
          </ul>
        </div>
        <div className="glass rounded-xl p-6">
          <div className="text-[10px] font-mono tracking-[0.3em] uppercase mb-3" style={{ color: 'var(--red-dead)' }}>
            For Next Year
          </div>
          <ul className="space-y-2 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            <li><strong style={{ color: 'var(--text-primary)' }}>1-seed upset coverage:</strong> Only 5.4% had Iowa over Florida — need more upset mass in later rounds</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Unified probability pipeline:</strong> Research and simulation modules diverged on calibration</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Mutation factor:</strong> 6% coin-flip mutation was designed but never wired in</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Strategy rebalance:</strong> More cinderella (15%→20%), less chalk (30%→25%)</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Live odds:</strong> Pre-tournament only — incorporate line movement during tournament</li>
          </ul>
        </div>
      </div>

      {/* Tech Stack */}
      <div className="glass rounded-xl p-6">
        <div className="text-[10px] font-mono tracking-[0.3em] uppercase mb-3" style={{ color: 'var(--orange)' }}>
          How It Was Built
        </div>
        <div className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>9-factor power index</strong> (KenPom AdjEM 53%, defensive efficiency, SOS, experience, luck, FT rate, coaching, injuries, 3PT variance)
          weighted into a <strong style={{ color: 'var(--text-primary)' }}>4-layer log-odds blend</strong> (Vegas market, statistical model, matchup analysis, qualitative factors)
          with <strong style={{ color: 'var(--text-primary)' }}>spread-adaptive weights</strong> (locks/lean/coin-flip tiers).
          206M brackets generated via <strong style={{ color: 'var(--text-primary)' }}>stratified importance sampling</strong> across
          5 temperature profiles (chalk, standard, smart upset, cinderella, chaos).
          Pruned in real-time via <strong style={{ color: 'var(--text-primary)' }}>validity bitmap architecture</strong> — immutable 206M table,
          pruning operates on 5 tiny alive-outcome tables (&lt;50ms per game).
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          {['Python', 'NumPy', 'PostgreSQL', 'FastAPI', 'React', 'Vite', 'Claude Code'].map((t) => (
            <span key={t} className="text-[10px] font-mono px-2 py-1 rounded" style={{ color: 'var(--orange)', background: 'rgba(255,107,53,0.08)', border: '1px solid rgba(255,107,53,0.15)' }}>
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Proof Footer */}
      <div className="text-center py-4">
        <div className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          Generated March 19, 2026 before tipoff — 206,000,000 brackets
        </div>
        <div className="text-[9px] font-mono mt-1" style={{ color: 'var(--orange)', wordBreak: 'break-all' }}>
          SHA-256: 6d9f395424b988a383e63720cd87482fa88c588f5ffa880db82b3fb2c6a68f84
        </div>
        <div className="text-[10px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          github.com/toannhuynh206/march-prediction
        </div>
      </div>
    </div>
  )
}
