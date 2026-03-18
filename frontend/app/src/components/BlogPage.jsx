/**
 * Blog / Research Paper page.
 *
 * Editorial magazine-style walkthrough of the entire project:
 * motivation, engineering process, agent architecture, math,
 * and the vision behind the bracket simulation engine.
 *
 * Pure CSS animations — no extra dependencies.
 */

import { useState, useEffect, useRef } from 'react'

// ---------------------------------------------------------------------------
// Scroll-triggered fade-in hook
// ---------------------------------------------------------------------------

function useReveal() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold: 0.12 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return { ref, visible }
}

function Reveal({ children, delay = 0, className = '' }) {
  const { ref, visible } = useReveal()
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(28px)',
        transition: `opacity 0.7s ease ${delay}s, transform 0.7s ease ${delay}s`,
      }}
    >
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tiny components
// ---------------------------------------------------------------------------

function SectionNumber({ n }) {
  return (
    <span
      className="font-display text-6xl sm:text-8xl leading-none select-none"
      style={{ color: 'var(--orange)', opacity: 0.12 }}
    >
      {String(n).padStart(2, '0')}
    </span>
  )
}

function SectionHeading({ number, title, subtitle }) {
  return (
    <Reveal>
      <div className="flex items-start gap-4 sm:gap-6 mb-8">
        <SectionNumber n={number} />
        <div>
          <h2
            className="font-display text-3xl sm:text-4xl md:text-5xl leading-tight tracking-wide"
            style={{ color: 'var(--text-primary)' }}
          >
            {title}
          </h2>
          {subtitle && (
            <p className="mt-1 text-sm sm:text-base" style={{ color: 'var(--text-secondary)' }}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
    </Reveal>
  )
}

function Prose({ children }) {
  return (
    <div
      className="max-w-[680px] text-base sm:text-lg leading-relaxed space-y-5"
      style={{ color: 'var(--text-secondary)' }}
    >
      {children}
    </div>
  )
}

function MathBlock({ label, children }) {
  return (
    <Reveal delay={0.1}>
      <div className="my-8 rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
        {label && (
          <div
            className="px-4 py-2 font-mono text-xs tracking-wider uppercase"
            style={{
              background: 'rgba(255, 107, 53, 0.06)',
              color: 'var(--orange)',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            {label}
          </div>
        )}
        <pre
          className="p-3 sm:p-6 font-mono text-[11px] sm:text-sm md:text-base leading-relaxed overflow-x-auto"
          style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)' }}
        >
          {children}
        </pre>
      </div>
    </Reveal>
  )
}

function CalloutCard({ accent = 'var(--orange)', icon, title, children }) {
  return (
    <Reveal delay={0.05}>
      <div
        className="rounded-xl p-5 sm:p-6 my-6"
        style={{
          background: 'var(--bg-card)',
          borderLeft: `3px solid ${accent}`,
          border: `1px solid var(--border-subtle)`,
          borderLeftColor: accent,
          borderLeftWidth: 3,
        }}
      >
        <div className="flex items-center gap-2 mb-2">
          {icon && <span className="text-lg">{icon}</span>}
          <span className="font-semibold text-sm uppercase tracking-wider" style={{ color: accent }}>
            {title}
          </span>
        </div>
        <div className="text-sm sm:text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {children}
        </div>
      </div>
    </Reveal>
  )
}

function DataTable({ headers, rows }) {
  return (
    <Reveal delay={0.1}>
      <div className="my-6 rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'rgba(255, 107, 53, 0.06)' }}>
                {headers.map((h, i) => (
                  <th
                    key={i}
                    className="px-4 py-3 text-left font-mono text-xs uppercase tracking-wider"
                    style={{ color: 'var(--orange)', borderBottom: '1px solid var(--border-subtle)' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} style={{ background: ri % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-card)' }}>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className="px-4 py-2.5 font-mono text-xs sm:text-sm"
                      style={{
                        color: ci === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
                        borderBottom: '1px solid var(--border-subtle)',
                      }}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Reveal>
  )
}

function AgentCard({ name, role, emoji, tools }) {
  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-2 glass glass-hover transition-all duration-300"
      style={{ minWidth: 200 }}
    >
      <div className="flex items-center gap-2">
        <span className="text-2xl">{emoji}</span>
        <span className="font-display text-lg tracking-wide" style={{ color: 'var(--text-primary)' }}>
          {name}
        </span>
      </div>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{role}</p>
      <div className="flex flex-wrap gap-1 mt-auto">
        {tools.map((t, i) => (
          <span
            key={i}
            className="text-[10px] font-mono px-2 py-0.5 rounded-full"
            style={{ background: 'rgba(255,107,53,0.08)', color: 'var(--orange)' }}
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}

function Divider() {
  return (
    <div className="my-16 sm:my-24 flex items-center gap-4">
      <div className="flex-1 h-px" style={{ background: 'linear-gradient(90deg, transparent, var(--border-subtle), transparent)' }} />
      <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--orange)', opacity: 0.4 }} />
      <div className="flex-1 h-px" style={{ background: 'linear-gradient(90deg, transparent, var(--border-subtle), transparent)' }} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Probability visualization
// ---------------------------------------------------------------------------

function ProbBar({ label, value, max = 1, color = 'var(--orange)' }) {
  const { ref, visible } = useReveal()
  const pct = Math.round((value / max) * 100)

  return (
    <div ref={ref} className="flex items-center gap-3 my-1.5">
      <span className="font-mono text-xs w-24 text-right" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <div className="flex-1 h-5 rounded-full overflow-hidden" style={{ background: 'var(--bg-surface)' }}>
        <div
          className="h-full rounded-full"
          style={{
            width: visible ? `${pct}%` : '0%',
            background: color,
            transition: 'width 1.2s cubic-bezier(0.22, 1, 0.36, 1)',
            opacity: 0.85,
          }}
        />
      </div>
      <span className="font-mono text-xs w-12" style={{ color: 'var(--text-secondary)' }}>{(value * 100).toFixed(1)}%</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table of contents (sticky side nav on desktop)
// ---------------------------------------------------------------------------

const TOC = [
  { id: 'motivation', label: 'Motivation' },
  { id: 'the-problem', label: 'The Problem' },
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'probability', label: 'Win Probability' },
  { id: 'log-odds', label: 'Log-Odds Blend' },
  { id: 'bracket-encoding', label: 'Bracket Encoding' },
  { id: 'enumeration', label: 'The Discovery' },
  { id: 'sharpening', label: 'Sharpening Rules' },
  { id: 'calibration', label: 'Historical Calibration' },
  { id: 'upset-decay', label: 'Upset Decay Curve' },
  { id: 'contrarian', label: 'The Contrarian Edge' },
  { id: 'agents', label: 'Agent Architecture' },
  { id: 'research', label: 'Research Pipeline' },
  { id: 'strategies', label: '11 Strategies' },
  { id: 'whats-next', label: "What's Next" },
]

function MobileToc({ activeId }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="lg:hidden sticky top-[52px] z-40 px-4 py-2" style={{
      backgroundColor: 'rgba(11, 14, 23, 0.92)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-between w-full py-1"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: 'var(--text-muted)' }}>
          Contents
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs truncate max-w-[160px]" style={{ color: 'var(--orange)' }}>
            {TOC.find((t) => t.id === activeId)?.label ?? ''}
          </span>
          <span
            className="text-xs transition-transform duration-200"
            style={{ color: 'var(--text-muted)', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
          >
            ▾
          </span>
        </div>
      </button>

      {open && (
        <div className="mt-2 pb-1 grid grid-cols-2 gap-x-4 gap-y-1">
          {TOC.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              onClick={() => setOpen(false)}
              className="block text-xs py-1.5 pl-3 transition-all duration-200"
              style={{
                color: activeId === item.id ? 'var(--orange)' : 'var(--text-muted)',
                borderLeft: activeId === item.id ? '2px solid var(--orange)' : '2px solid transparent',
                fontWeight: activeId === item.id ? 600 : 400,
              }}
            >
              {item.label}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function TableOfContents({ activeId }) {
  return (
    <>
      {/* Desktop: fixed side nav — pushed below sticky header */}
      <nav className="hidden lg:block fixed right-8 w-44 space-y-0.5 max-h-[70vh] overflow-y-auto"
        style={{ scrollbarWidth: 'none', top: '50%', transform: 'translateY(-50%)' }}
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] block mb-3" style={{ color: 'var(--text-muted)' }}>
          Contents
        </span>
        {TOC.map((item) => (
          <a
            key={item.id}
            href={`#${item.id}`}
            className="block text-xs py-1 pl-3 transition-all duration-200"
            style={{
              color: activeId === item.id ? 'var(--orange)' : 'var(--text-muted)',
              borderLeft: activeId === item.id ? '2px solid var(--orange)' : '2px solid transparent',
              fontWeight: activeId === item.id ? 600 : 400,
            }}
          >
            {item.label}
          </a>
        ))}
      </nav>

      {/* Mobile/Tablet: sticky collapsible TOC */}
      <MobileToc activeId={activeId} />
    </>
  )
}

// ---------------------------------------------------------------------------
// Main Blog Page
// ---------------------------------------------------------------------------

export default function BlogPage() {
  const [activeSection, setActiveSection] = useState('motivation')

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id)
          }
        }
      },
      { rootMargin: '-20% 0px -70% 0px' },
    )

    for (const { id } of TOC) {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [])

  return (
    <div className="relative">
      <TableOfContents activeId={activeSection} />

      <article className="max-w-[760px] mx-auto px-4 sm:px-6">

        {/* ── Hero ── */}
        <Reveal>
          <header className="pt-8 pb-12 sm:pt-12 sm:pb-16">
            <div className="flex items-center gap-3 mb-6">
              <div className="h-px flex-1" style={{ background: 'linear-gradient(90deg, var(--orange), transparent)' }} />
              <span className="font-mono text-[10px] tracking-[0.3em] uppercase" style={{ color: 'var(--orange)' }}>
                Research Paper
              </span>
              <div className="h-px flex-1" style={{ background: 'linear-gradient(270deg, var(--orange), transparent)' }} />
            </div>

            <h1
              className="font-display text-4xl sm:text-6xl md:text-7xl leading-[0.95] tracking-wide text-center"
              style={{ color: 'var(--text-primary)' }}
            >
              Beating March Madness
              <span className="block mt-1" style={{ color: 'var(--orange)' }}>With Mathematics</span>
            </h1>

            <p className="text-center mt-6 text-sm sm:text-base max-w-lg mx-auto leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              How we built an AI-powered bracket simulation engine that enumerates
              every possible outcome, blends Vegas odds with advanced statistics,
              and generates 206 million strategically targeted brackets.
            </p>

            <div className="flex flex-wrap justify-center gap-4 sm:gap-6 mt-8">
              <div className="text-center">
                <span className="font-display text-xl sm:text-3xl" style={{ color: 'var(--cyan)' }}>206M</span>
                <span className="block font-mono text-[9px] sm:text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>brackets generated</span>
              </div>
              <div className="text-center">
                <span className="font-display text-xl sm:text-3xl" style={{ color: 'var(--orange)' }}>9.2 QN</span>
                <span className="block font-mono text-[9px] sm:text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>total possible brackets</span>
              </div>
              <div className="text-center">
                <span className="font-display text-xl sm:text-3xl" style={{ color: 'var(--green-alive)' }}>11</span>
                <span className="block font-mono text-[9px] sm:text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>targeting strategies</span>
              </div>
            </div>
          </header>
        </Reveal>

        <Divider />

        {/* ── 01. Motivation ── */}
        <section id="motivation">
          <SectionHeading number={1} title="MOTIVATION" subtitle="Narrowing the impossible" />
          <Reveal>
            <Prose>
              <p>
                There are roughly
                <strong style={{ color: 'var(--text-primary)' }}> 9.2 quintillion </strong>
                possible brackets. That's 9,223,372,036,854,775,808. If you printed one
                bracket per second, you'd need longer than the age of the universe to
                finish. The search space is, for all practical purposes, infinite.
              </p>
              <p>
                Imagine someone hands you a single, specific rock and says: <em>"Find
                this exact rock somewhere on Earth."</em> You'd never do it. The planet
                is too vast. But what if you knew it came from a certain country?
                A certain mountain range? A specific riverbed? Each piece of
                information{' '}
                <strong style={{ color: 'var(--orange)' }}>narrows the search space</strong>{' '}
                — transforms an impossible task into a tractable one.
              </p>
              <p>
                That's the core idea behind this project. We're not trying to predict
                a perfect bracket — nobody can. We're trying to{' '}
                <strong style={{ color: 'var(--orange)' }}>
                  shrink 9.2 quintillion possibilities down to a region we can actually explore.
                </strong>{' '}
                Every tool at our disposal serves this one purpose:
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-6">
              {[
                { icon: '📊', label: 'Information', desc: 'KenPom stats, injury reports, market odds — data eliminates impossible corners of the space.' },
                { icon: '📐', label: 'Mathematics', desc: 'Logistic models, Bayesian updating, calibration — math quantifies which regions are most likely.' },
                { icon: '🧠', label: 'Gut Feelings', desc: 'Coaching instincts, eye-test adjustments, matchup intuition — human judgment fills gaps data can\'t.' },
                { icon: '🎯', label: 'Diverse Portfolio', desc: 'Multiple strategy profiles — chalk, contrarian, chaos — ensure we cover the right neighborhoods.' },
              ].map((item, i) => (
                <div key={i} className="p-4 rounded-lg" style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--border-subtle)',
                }}>
                  <div className="text-lg mb-1">{item.icon}</div>
                  <div className="font-mono text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--orange)' }}>{item.label}</div>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>{item.desc}</p>
                </div>
              ))}
            </div>
          </Reveal>

          <Reveal delay={0.15}>
            <Prose>
              <p>
                None of these tools alone solves the problem. But layered together, each one
                carves away vast swaths of the search space. Stats eliminate the
                obviously wrong. Math ranks what's left. Intuition breaks ties.
                And a diversified portfolio ensures we're not all-in on a single
                narrow path through the bracket.
              </p>
              <p>
                The goal isn't perfection — it's{' '}
                <strong style={{ color: 'var(--text-primary)' }}>
                  reduction
                </strong>
                . Go from the whole world to a country. From a country to a city.
                From a city to a neighborhood. That's the game.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 02. The Problem ── */}
        <section id="the-problem">
          <SectionHeading number={2} title="THE PROBLEM" subtitle="What are we actually solving?" />
          <Reveal>
            <Prose>
              <p>
                The NCAA Tournament is a 63-game single-elimination bracket. Four regions of
                16 teams each play down to a regional champion, then the four champions meet
                in the Final Four. You predict every game. Points escalate each round:
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Round', 'Games', 'Points/Correct Pick', 'Cumulative Weight']}
            rows={[
              ['Round of 64', '32', '10', '320 pts available'],
              ['Round of 32', '16', '20', '320 pts available'],
              ['Sweet 16', '8', '40', '320 pts available'],
              ['Elite 8', '4', '80', '320 pts available'],
              ['Final Four', '2', '160', '320 pts available'],
              ['Championship', '1', '320', '320 pts available'],
            ]}
          />

          <Reveal delay={0.1}>
            <Prose>
              <p>
                Notice something? Each round is worth <strong style={{ color: 'var(--text-primary)' }}>exactly 320 points total</strong>.
                The championship game alone is worth as much as getting every single
                first-round game right. This scoring system heavily rewards getting
                the later rounds correct — which means your champion pick matters
                enormously.
              </p>
              <p>
                The naive approach is to fill out one bracket with your gut feelings.
                The problem: your gut feelings are probably similar to millions of
                other people's. If you and 40% of the pool all pick Duke to win,
                you're sharing that upside with everyone.
              </p>
            </Prose>
          </Reveal>

          <CalloutCard accent="var(--cyan)" icon="💡" title="Key Insight">
            The goal isn't predicting every game correctly — it's{' '}
            <strong>narrowing the search space</strong> so that the brackets we generate
            live in the most probable region of 9.2 quintillion possibilities.
          </CalloutCard>
        </section>

        <Divider />

        {/* ── 03. How It Works ── */}
        <section id="how-it-works">
          <SectionHeading number={3} title="HOW IT WORKS" subtitle="The complete data pipeline" />
          <Reveal>
            <Prose>
              <p>
                Before diving into the details, here's the complete pipeline — six stages
                that transform raw research into 206 million strategically targeted brackets.
                Each stage feeds the next. The brackets and their probabilities aren't
                scored separately — they{' '}
                <strong style={{ color: 'var(--orange)' }}>emerge together</strong> from the math.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.05}>
            <div className="space-y-3 my-8">
              {[
                {
                  stage: '1',
                  title: 'Research → Raw Data',
                  color: 'var(--cyan)',
                  desc: 'Web searches, KenPom scraping, odds API calls, injury reports, coaching records. This produces raw numbers for all 64 teams: efficiency margins, tempo, defensive ratings, experience scores, moneylines, and more.',
                },
                {
                  stage: '2',
                  title: 'Power Index → One Number Per Team',
                  color: 'var(--cyan)',
                  desc: 'A 9-factor weighted formula (AdjEM 40%, defensive premium 10%, schedule strength 10%, etc.) collapses each team\'s raw data into a single power index on a 0–100 scale. Every team gets one number that represents their overall strength.',
                },
                {
                  stage: '3',
                  title: 'Win Probabilities → One Number Per Matchup',
                  color: 'var(--orange)',
                  desc: 'A logistic function converts the power index differential between any two teams into a win probability. Then a 4-layer log-odds blend (market, stats, matchup, qualitative factors) produces a final P(A beats B) for every possible pairing.',
                },
                {
                  stage: '4',
                  title: 'Regional Enumeration → 32,768 Exact Brackets',
                  color: 'var(--orange)',
                  desc: 'For each of the 2\u00B9\u2075 possible outcome combinations in a region, the code traces through round by round, looks up the conditional matchup probability for whoever actually advances, and multiplies them together. Each bracket gets an exact probability. No sampling, no randomness — pure enumeration.',
                },
                {
                  stage: '5',
                  title: 'Strategy + Combination → 206M Full Brackets',
                  color: 'var(--red-dead)',
                  desc: 'Temperature transforms and 11 strategy profiles re-weight the base probabilities to create diversity. Then 4 regional brackets are combined (one from each region), Final Four outcomes are simulated, and you get a 63-bit full tournament bracket with a combined probability.',
                },
                {
                  stage: '6',
                  title: 'Live Pruning → Survivors',
                  color: 'var(--red-dead)',
                  desc: 'As real games are played, a SQL bitwise operation eliminates every bracket that got a game wrong. Surviving brackets\' weights get renormalized. What survives becomes the live prediction for the next round.',
                },
              ].map((item) => (
                <Reveal key={item.stage} delay={0.03 * Number(item.stage)}>
                  <div
                    className="flex gap-4 rounded-xl p-4 sm:p-5"
                    style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-subtle)',
                      borderLeftColor: item.color,
                      borderLeftWidth: 3,
                    }}
                  >
                    <div className="flex-shrink-0">
                      <span
                        className="font-display text-2xl sm:text-3xl leading-none"
                        style={{ color: item.color, opacity: 0.7 }}
                      >
                        {item.stage}
                      </span>
                    </div>
                    <div>
                      <h3
                        className="font-display text-base sm:text-lg tracking-wide mb-1"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {item.title}
                      </h3>
                      <p className="text-xs sm:text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                        {item.desc}
                      </p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </Reveal>

          <CalloutCard accent="var(--orange)" icon="&#9889;" title="Key Insight">
            The research and math don't score brackets <em>after</em> generation — they define
            the probability space that enumeration walks through. The brackets and their
            probabilities emerge together in one pass. Stage 4 isn't "generate then evaluate" —
            it's "enumerate every possibility and compute its exact likelihood simultaneously."
          </CalloutCard>

          <Reveal delay={0.1}>
            <Prose>
              <p>
                The sections that follow dive deep into each stage. But remember:
                this pipeline is a{' '}
                <strong style={{ color: 'var(--text-primary)' }}>funnel</strong>.
                9.2 quintillion possibilities enter at the top. Research eliminates the
                impossible. Math ranks what's left. Strategy diversifies across the
                best candidates. And live pruning tells you which of your picks
                are still standing.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 04. Win Probability ── */}
        <section id="probability">
          <SectionHeading number={4} title="WIN PROBABILITY" subtitle="Predicting who wins each game" />
          <Reveal>
            <Prose>
              <p>
                Before we can build brackets, we need the fundamental building block:
                <strong style={{ color: 'var(--text-primary)' }}> P(Team A beats Team B)</strong> for every possible matchup.
                We compute this from three independent signals, each capturing different information.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              Signal 1: The Power Index
            </h3>
            <Prose>
              <p>
                Every team gets a single number (0–100) called a <strong style={{ color: 'var(--text-primary)' }}>power index</strong>.
                It's a weighted composite of nine factors:
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Factor', 'Weight', 'What It Measures']}
            rows={[
              ['Adjusted Efficiency Margin', '40%', 'Points scored minus points allowed per 100 possessions, adjusted for opponent strength'],
              ['Defensive Premium', '10%', 'Elite defense wins in March — half-court execution under pressure'],
              ['Non-Conference SOS', '10%', 'Schedule strength outside your conference bubble'],
              ['Experience Score', '10%', 'Upperclassmen vs. freshmen — poise under pressure'],
              ['Luck Adjustment', '8%', 'How much of their record was close-game variance'],
              ['Free Throw Rate', '7%', 'Games tighten in March — FT shooting wins close ones'],
              ['Coaching Score', '7%', 'Historical March tournament performance (Izzo, Self, etc.)'],
              ['Key Injuries', '5%', 'Hard point adjustment for missing starters'],
              ['3-Point Variance', '3%', 'Volatile 3PT shooting = risky — hot/cold swings'],
            ]}
          />

          <Reveal delay={0.1}>
            <Prose>
              <p>
                The single most predictive stat in college basketball is <strong style={{ color: 'var(--orange)' }}>Adjusted Efficiency Margin (AdjEM)</strong>,
                which gets 40% of the weight. It answers: "If this team played an average opponent
                100 times, how many more points would they score per 100 possessions?" Duke might be +28.
                A 16-seed might be -5. That 33-point gap translates directly into win probability.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              Signal 2: Vegas Market Odds
            </h3>
            <Prose>
              <p>
                Sportsbooks set point spreads for every tournament game. Duke -14.5 vs. High Point means
                Vegas expects Duke to win by about 14.5 points. We convert spreads to probabilities using
                the cumulative normal distribution:
              </p>
            </Prose>
          </Reveal>

          <MathBlock label="Spread → Probability">
{`P(favorite wins) = Φ(spread / σ)

where Φ = standard normal CDF
      σ ≈ 11 (college basketball scoring variance)

Example: Duke -14.5
  P = Φ(14.5 / 11) = Φ(1.318) ≈ 90.6%`}
          </MathBlock>

          <CalloutCard accent="var(--gold)" icon="💰" title="Why Trust Vegas?">
            Bookmakers have millions of dollars riding on accuracy. Their lines are the single
            most accurate publicly available prediction — better than any model, any expert,
            any algorithm. They aggregate all available information into one number. We de-vig
            (remove the profit margin) to get fair probabilities.
          </CalloutCard>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              Signal 3: Qualitative Factors
            </h3>
            <Prose>
              <p>
                The third signal captures things raw numbers miss: coaching pedigree in March,
                tempo mismatches (slow teams compress variance, which helps underdogs),
                and historical seed upset rates. A 12-seed has beaten a 5-seed
                in 35.6% of all matchups since 1985 — the public consistently
                underestimates this.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="my-8 rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
              <span className="font-mono text-xs uppercase tracking-wider block mb-4" style={{ color: 'var(--orange)' }}>
                Historical Upset Rates (1985–2024)
              </span>
              <ProbBar label="1 vs 16" value={0.013} color="var(--green-alive)" />
              <ProbBar label="2 vs 15" value={0.065} color="var(--green-alive)" />
              <ProbBar label="3 vs 14" value={0.150} color="var(--cyan)" />
              <ProbBar label="4 vs 13" value={0.210} color="var(--cyan)" />
              <ProbBar label="5 vs 12" value={0.356} color="var(--orange)" />
              <ProbBar label="6 vs 11" value={0.370} color="var(--orange)" />
              <ProbBar label="7 vs 10" value={0.390} color="var(--orange)" />
              <ProbBar label="8 vs 9" value={0.519} color="var(--red-dead)" />
              <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                Percentage = rate at which the lower seed (underdog) wins. 8 vs 9 is basically a coin flip — the 9-seed actually wins more often.
              </p>
            </div>
          </Reveal>
        </section>

        <Divider />

        {/* ── 04. Log-Odds Blend ── */}
        <section id="log-odds">
          <SectionHeading number={5} title="THE LOG-ODDS BLEND" subtitle="Why we can't just average probabilities" />
          <Reveal>
            <Prose>
              <p>
                We have three signals — market, stats, and factors — each producing
                a win probability. The naive approach is to average them. But averaging
                probabilities gives mathematically wrong answers:
              </p>
            </Prose>
          </Reveal>

          <MathBlock label="The Wrong Way — Direct Average">
{`Vegas says:  P = 95%  (Duke crushes)
Stats say:   P = 50%  (it's a toss-up)

Simple average = (95% + 50%) / 2 = 72.5%

This underweights the strength of the 95% signal.
Vegas is extremely confident — a simple average
dilutes that confidence too much.`}
          </MathBlock>

          <Reveal>
            <Prose>
              <p>
                The solution is to blend in <strong style={{ color: 'var(--text-primary)' }}>log-odds space</strong> (also called logit space).
                The logit function transforms probability from the bounded range (0, 1)
                into an unbounded range (-∞, +∞):
              </p>
            </Prose>
          </Reveal>

          <MathBlock label="Logit Transform">
{`logit(p) = ln(p / (1 - p))

logit(0.50) =  0.00    (no edge either way)
logit(0.75) =  1.10    (moderate favorite)
logit(0.95) =  2.94    (strong favorite)
logit(0.99) =  4.60    (near-certain)

The transform stretches extreme probabilities apart,
giving strong signals proportionally more influence.`}
          </MathBlock>

          <MathBlock label="The Right Way — Log-Odds Blend">
{`P_final = sigmoid(
    0.55 × logit(P_market)     ← Vegas (most accurate)
  + 0.25 × logit(P_stats)      ← Power index model
  + 0.12 × logit(P_matchup)    ← Style/tempo factors
  + 0.08 × logit(P_factors)    ← Coaching, history
)

Example:
  0.55 × logit(0.95) + 0.25 × logit(0.50)
= 0.55 × 2.94  +  0.25 × 0.00
= 1.617

sigmoid(1.617) = 83.4%

Much more reasonable — the strong Vegas signal
is respected, not diluted.`}
          </MathBlock>

          <CalloutCard accent="var(--cyan)" icon="📐" title="Why This Matters">
            Log-odds blending is the same math used in Bayesian statistics
            to combine evidence from multiple independent sources. Each signal
            contributes "evidence" proportional to its weight, and the sigmoid
            function converts the accumulated evidence back into a probability.
            It's the mathematically correct way to fuse predictions.
          </CalloutCard>
        </section>

        <Divider />

        {/* ── 05. Bracket Encoding ── */}
        <section id="bracket-encoding">
          <SectionHeading number={6} title="BRACKET ENCODING" subtitle="63 games as a binary number" />
          <Reveal>
            <Prose>
              <p>
                A March Madness bracket is 63 games. Each game has exactly two outcomes:
                the favorite wins (0) or the underdog wins (1). That means every bracket
                is a <strong style={{ color: 'var(--text-primary)' }}>63-bit binary number</strong>.
              </p>
              <p>
                We split the 63 bits into four regions of 15 games each, plus 3 Final Four games:
              </p>
            </Prose>
          </Reveal>

          <MathBlock label="63-Bit Bracket Layout">
{`[ South: 15 bits ][ East: 15 bits ][ West: 15 bits ][ Midwest: 15 bits ][ F4: 3 bits ]
   bits 0-14          bits 15-29        bits 30-44         bits 45-59       bits 60-62

Within each 15-bit region:
  Round of 64:  8 games  →  bits 0-7     (1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15)
  Round of 32:  4 games  →  bits 8-11    (winners face off)
  Sweet 16:     2 games  →  bits 12-13
  Elite 8:      1 game   →  bit 14       (regional final)

Bit = 0  →  higher seed (favorite) wins
Bit = 1  →  lower seed (upset) wins

Example: bracket integer 0 = 000...000 = every favorite wins = "perfect chalk"`}
          </MathBlock>

          <Reveal>
            <Prose>
              <p>
                This encoding is a <strong style={{ color: 'var(--text-primary)' }}>perfect bijection</strong> — every integer from
                0 to 32,767 maps to exactly one valid regional bracket, and every
                regional bracket maps to exactly one integer. No wasted space, no
                ambiguity. We can store, compare, and manipulate brackets as simple
                integers.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 06. The Discovery ── */}
        <section id="enumeration">
          <SectionHeading number={7} title="THE DISCOVERY" subtitle="Enumerate, don't sample" />
          <Reveal>
            <Prose>
              <p>
                The original plan was Monte Carlo simulation: randomly generate millions of
                brackets per region by rolling weighted dice for each game. This is what
                most bracket tools do. But we discovered something that changed everything:
              </p>
            </Prose>
          </Reveal>

          <CalloutCard accent="var(--orange)" icon="🔥" title="The Breakthrough">
            Each region has exactly <strong>2^15 = 32,768</strong> possible brackets.
            That's a tiny number. A laptop can enumerate all of them and compute
            exact probabilities in under one second. No sampling. No approximation.
            Zero error.
          </CalloutCard>

          <Reveal>
            <Prose>
              <p>
                The probability of any regional bracket is the product of the probability
                of each game outcome along the bracket path:
              </p>
            </Prose>
          </Reveal>

          <MathBlock label="Exact Bracket Probability">
{`P(bracket) = ∏ P(game_outcome)
              for all 15 games

All-chalk South example:
  P = P(1 beats 16) × P(8 beats 9) × P(5 beats 12) × P(4 beats 13)
    × P(6 beats 11) × P(3 beats 14) × P(7 beats 10) × P(2 beats 15)
    × P(1 beats 8)  × P(4 beats 5)  × P(3 beats 6)  × P(2 beats 7)
    × P(1 beats 4)  × P(2 beats 3)  × P(1 beats 2)

Important: later-round probabilities are CONDITIONAL.
  P(1 beats 8 in R32) is different from P(1 beats 9 in R32).
  The code traces who actually reaches each game.`}
          </MathBlock>

          <Reveal>
            <Prose>
              <p>
                We use log-probabilities (sum of logs instead of product) to avoid
                numerical underflow — when you multiply 15 probabilities together,
                the numbers get extremely small. Taking the log turns multiplication
                into addition, which is both faster and more numerically stable.
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Metric', 'Monte Carlo (51.5M sampled)', 'Enumeration (all 32,768)']}
            rows={[
              ['Probability accuracy', 'Approximate (sampling error)', 'Exact (zero error)'],
              ['Storage per region', '~1.7 GB', '~1.8 MB'],
              ['Time per region', 'Minutes', '< 1 second'],
              ['Duplicate brackets', 'Possible', 'Impossible (every bracket unique)'],
              ['Coverage', '~1,570x oversampling', '100% of possibility space'],
            ]}
          />

          <Reveal delay={0.1}>
            <Prose>
              <p>
                The catch: full brackets combine 4 regions plus 3 Final Four games,
                giving 32,768^4 × 8 = 9.2 quintillion possibilities. We can't
                enumerate those. So we use a <strong style={{ color: 'var(--text-primary)' }}>hybrid approach</strong>: enumerate
                regions exactly, then generate 206 million cross-region combinations
                using stratified importance sampling — weighted by exact regional
                probabilities, with a 6% mutation X-factor on coin-flip games.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 07. Sharpening ── */}
        <section id="sharpening">
          <SectionHeading number={8} title="SHARPENING RULES" subtitle="Eliminating the impossible" />
          <Reveal>
            <Prose>
              <p>
                Not all 32,768 regional brackets deserve consideration. A bracket
                where a 16-seed wins the region has happened exactly zero times in
                tournament history. We "sharpen" the space with hard constraints:
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Rule', 'Constraint', 'Effect']}
            rows={[
              ['1-seed auto-advance', '1-seeds always win R64', 'Bit 0 locked to 0 (99.3% historically)'],
              ['2-seed auto-advance', '2-seeds always win R64', 'Bit 7 locked to 0 (93.5% historically)'],
              ['16-seed ceiling', 'No 16-seed past R64', 'Eliminates 16-seed bracket paths'],
              ['15-seed ceiling', 'No 15-seed past R32', 'Saint Peter\'s 2022 was a unicorn'],
              ['14-seed ceiling', 'No 14-seed past R32', 'Has literally never happened'],
              ['Min 12-over-5', 'At least one 12/5 upset in tournament', 'Happens ~85% of years'],
            ]}
          />

          <Reveal delay={0.1}>
            <Prose>
              <p>
                Locking just two bits (1-seed and 2-seed auto-advance in R64) cuts
                the live space from 32,768 to <strong style={{ color: 'var(--text-primary)' }}>8,192 brackets per region</strong>.
                The remaining rules eliminate hundreds more. We focus our entire
                computation budget on brackets that could actually happen.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 08. Historical Calibration ── */}
        <section id="calibration">
          <SectionHeading number={9} title="HISTORICAL CALIBRATION" subtitle="The Polacheck Method — 40 years of base rates" />
          <Reveal>
            <Prose>
              <p>
                Before we trust our model, we need to validate it against reality.
                The <strong style={{ color: 'var(--text-primary)' }}>Polacheck Method</strong> analyzed
                40 years of NCAA tournament data (1985–2024) to answer a simple question:
                what does the <em>statistically most common</em> bracket actually look like?
              </p>
              <p>
                This isn't about predicting upsets — it's about knowing the
                <strong style={{ color: 'var(--orange)' }}> base rates</strong> our simulation
                must match. If our model produces champion distributions or upset frequencies
                that deviate wildly from 40 years of history, something is miscalibrated.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              Champion Seed Distribution
            </h3>
            <Prose>
              <p>
                A 1-seed has won the championship <strong style={{ color: 'var(--text-primary)' }}>25 out of 40 tournaments</strong> — a
                62.5% rate. This is our most important calibration target. If our simulation
                produces 1-seed champions at 45% or 80%, we know we're off.
              </p>
            </Prose>
          </Reveal>

          <div className="my-8 rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
            <Reveal>
              <span className="font-mono text-xs uppercase tracking-wider block mb-4" style={{ color: 'var(--orange)' }}>
                Champion by Seed — Historical (1985–2024)
              </span>
              <ProbBar label="1-seed" value={0.628} color="var(--orange)" />
              <ProbBar label="2-seed" value={0.171} color="var(--cyan)" />
              <ProbBar label="3-seed" value={0.086} color="var(--cyan)" />
              <ProbBar label="4-seed" value={0.029} color="var(--text-muted)" />
              <ProbBar label="7-seed" value={0.029} color="var(--text-muted)" />
              <ProbBar label="8-seed" value={0.029} color="var(--text-muted)" />
              <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                No 5-seed or 6-seed has ever won the tournament. Seeds 4+ account for less than 12% combined.
              </p>
            </Reveal>
          </div>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              Final Four Composition
            </h3>
            <Prose>
              <p>
                The most common Final Four is <strong style={{ color: 'var(--orange)' }}>1-1-2-3</strong>: two
                1-seeds, one 2-seed, and one 3-or-4 seed. 1-seeds make up 40% of all
                Final Four appearances, 2-seeds 20%, 3-seeds 12%, and 4-seeds 9%.
                Everything else is 19% combined.
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Seed', 'Final Four %', 'Champion %', 'Calibration Use']}
            rows={[
              ['1', '40.0%', '62.8%', 'Primary anchor — must be ≥ 35%'],
              ['2', '20.0%', '17.1%', 'Secondary anchor — 15-25% target'],
              ['3', '12.0%', '8.6%', 'Tertiary — 8-16% target'],
              ['4', '9.0%', '2.9%', 'Ceiling starts here for champions'],
              ['5-8', '~12%', '~6%', 'Rare but not impossible'],
              ['9-16', '~7%', '~0%', 'Cinderella — validate isn\'t over-producing'],
            ]}
          />

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              The "Most Likely" R64 Composition
            </h3>
            <Prose>
              <p>
                Polacheck's key finding: the statistically most common Round of 64 outcome has
                <strong style={{ color: 'var(--text-primary)' }}> exactly 8 upsets</strong> across
                all 32 games. Not 4 (too chalky), not 12 (too chaotic). Here's the breakdown:
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Matchup', 'Upset Rate', 'Most Common # of Upsets (of 4)', 'Distribution']}
            rows={[
              ['1 vs 16', '1.3%', '0 upsets', '97% have zero upsets'],
              ['2 vs 15', '6.5%', '0 upsets', '80% have zero upsets'],
              ['3 vs 14', '15.0%', '0 upsets', '60% have zero, 30% have one'],
              ['4 vs 13', '21.0%', '1 upset', '55% have exactly one'],
              ['5 vs 12', '35.6%', '2 upsets', '35% have a 2-2 split — the classic'],
              ['6 vs 11', '37.0%', '2 upsets', '45% have a 2-2 split'],
              ['7 vs 10', '39.0%', '1 upset', '50% have 3 of 4 7-seeds advancing'],
              ['8 vs 9', '51.9%', '2 upsets', 'Nearly a coin flip — all outcomes common'],
            ]}
          />

          <CalloutCard accent="var(--cyan)" icon="🎯" title="Calibration Target">
            These distributions define the "worlds" in our stratified sampling.
            Each world is characterized by its upset count pattern (e.g., "2 upsets in 5v12,
            1 upset in 4v13, 2 upsets in 8v9"). The probability of each world comes directly
            from these 40-year base rates. Our simulation budget is allocated proportional to
            √P(world) — spending more compute on likely scenarios while still covering outliers.
          </CalloutCard>

          <Reveal delay={0.1}>
            <Prose>
              <p>
                We've integrated these targets into an <strong style={{ color: 'var(--text-primary)' }}>11th strategy profile</strong> called
                "Historical Base Rate" — brackets built to match the statistically most common
                tournament composition. It serves as a calibration anchor in our Core tier.
                If a bracket matches 40 years of history, it's not the most exciting pick,
                but it's the most <em>reliable</em> one.
              </p>
              <p>
                The real power is using these base rates as
                <strong style={{ color: 'var(--orange)' }}> validation checks</strong>.
                After generating all our brackets, we compare the aggregate output against
                these distributions. If our champion seed rates or upset frequencies deviate
                by more than 2σ from historical norms, we know our model has a bias to fix.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 09. Upset Decay Curve ── */}
        <section id="upset-decay">
          <SectionHeading number={10} title="THE UPSET DECAY CURVE" subtitle="Round-by-round chaos analysis — 5 years of data" />
          <Reveal>
            <Prose>
              <p>
                Historical calibration tells us <em>what</em> the average tournament looks like.
                But to build better brackets, we need to understand <strong style={{ color: 'var(--text-primary)' }}>when</strong> and
                <strong style={{ color: 'var(--text-primary)' }}> where</strong> upsets actually happen — round by round.
                We analyzed every game from 2021–2025 to map the <strong style={{ color: 'var(--orange)' }}>upset decay curve</strong>:
                the pattern of how upset frequency drops as the tournament progresses.
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Year', 'Champion', 'R64 (32g)', 'R32 (16g)', 'S16 (8g)', 'E8 (4g)', 'F4 (2g)', 'Final', 'Total']}
            rows={[
              ['2021', '1-seed', '10', '5', '2', '1', '1', '0', '19'],
              ['2022', '1-seed', '7', '5', '1', '2', '0', '0', '15'],
              ['2023', '4-seed', '6', '3', '2', '1', '1', '0', '13'],
              ['2024', '1-seed', '9', '1', '0', '2', '1', '0', '13'],
              ['2025', '1-seed', '7', '1', '0', '0', '0', '0', '8'],
              ['AVG', '—', '7.8', '3.0', '1.0', '1.2', '0.6', '0.0', '13.6'],
            ]}
          />

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              The Stories Behind the Numbers
            </h3>
            <Prose>
              <p>
                <strong style={{ color: 'var(--orange)' }}>2021 — Record Chaos.</strong>{' '}
                Oral Roberts (15-seed) stunned Ohio State and Florida. UCLA (11) went on a magical run
                to the Final Four. Oregon State (12) reached the Elite 8. Syracuse (11) made the Sweet 16.
                The most upset-heavy tournament in recent memory with 19 total upsets.
              </p>
              <p>
                <strong style={{ color: 'var(--orange)' }}>2022 — St. Peter's.</strong>{' '}
                The Peacocks (15-seed) became the lowest seed to reach the Elite 8 since 1997.
                UNC (8) beat 1-seed Baylor. Miami (10) reached the Elite 8. Five upsets in the
                Round of 32 kept the chaos flowing through the second weekend.
              </p>
              <p>
                <strong style={{ color: 'var(--orange)' }}>2023 — FDU Makes History.</strong>{' '}
                Fairleigh Dickinson (16) beat 1-seed Purdue — only the second 16-over-1 ever.
                Princeton (15) reached the Sweet 16. UConn won as a 4-seed, the lowest champion
                seed since 2014. A weird year where the "favorite" wasn't really a favorite.
              </p>
              <p>
                <strong style={{ color: 'var(--orange)' }}>2024 — The Template.</strong>{' '}
                9 upsets in the Round of 64 — the most day-1 chaos in years. But then? Only 1 upset
                in the Round of 32. Zero in the Sweet 16. The talent wall came down hard.
                NC State (11) was the lone Cinderella, riding an improbable run all the way to
                the championship game. Pattern: <em>chaos day 1, then talent wins.</em>
              </p>
              <p>
                <strong style={{ color: 'var(--orange)' }}>2025 — Historically Chalk.</strong>{' '}
                All four 1-seeds made the Final Four for the first time since 2008. Only 7 R64
                upsets, just 1 in the R32 (Arkansas over St. John's), and zero upsets from the
                Sweet 16 onward. The most dominant display of top-seed talent in modern history.
                Total: just 8 upsets — the lowest we've tracked.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              The Decay Pattern
            </h3>
            <Prose>
              <p>
                The data reveals a sharp, consistent pattern: upsets are concentrated in
                the <strong style={{ color: 'var(--text-primary)' }}>Round of 64</strong> and
                fall off a cliff in later rounds. We model this as a decay multiplier applied to
                each round's base upset probability:
              </p>
            </Prose>
          </Reveal>

          <div className="my-8 rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
            <Reveal>
              <span className="font-mono text-xs uppercase tracking-wider block mb-4" style={{ color: 'var(--orange)' }}>
                Upset Rate by Round — Historical Average (2021–2025)
              </span>
              <ProbBar label="R64" value={0.244} color="var(--orange)" />
              <ProbBar label="R32" value={0.188} color="var(--orange)" />
              <ProbBar label="S16" value={0.125} color="var(--cyan)" />
              <ProbBar label="E8" value={0.300} max={1} color="var(--cyan)" />
              <ProbBar label="F4" value={0.300} max={1} color="var(--text-muted)" />
              <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                E8 and F4 rates appear elevated due to tiny sample sizes (4 and 2 games per tournament).
                The underlying talent gap still widens each round.
              </p>
            </Reveal>
          </div>

          <MathBlock label="2026 Round Decay Multipliers">
{`Round   │  Historical  │  2026 Target  │  Rationale
────────┼──────────────┼───────────────┼─────────────────────────
R64     │    1.00x     │    1.00x      │  Baseline — mid-majors can still punch
R32     │    0.78x     │    0.70x      │  Talent wall arrives earlier (NIL/portal)
S16     │    0.52x     │    0.40x      │  Top teams dominate from here
E8      │    0.45x     │    0.35x      │  Very chalky — elite talent separates
F4      │    0.35x     │    0.25x      │  Expect 1/2-seeds dominating
Final   │    0.30x     │    0.20x      │  Near-certain better seed wins`}
          </MathBlock>

          <Reveal delay={0.05}>
            <h3 className="font-display text-xl sm:text-2xl tracking-wide mt-10 mb-4" style={{ color: 'var(--text-primary)' }}>
              2026 Thesis: Three Possible Worlds
            </h3>
            <Prose>
              <p>
                Rather than targeting a single upset count, we model{' '}
                <strong style={{ color: 'var(--orange)' }}>three tournament shapes</strong> — distinct
                "worlds" the 2026 tournament could fall into. Our simulation allocates bracket budget
                across all three, weighted by their probability:
              </p>
            </Prose>
          </Reveal>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-8">
            {[
              {
                name: 'CHALK',
                weight: '35%',
                color: 'var(--cyan)',
                upsets: '7-1-0-0-0',
                total: 8,
                desc: '2025-like. Top seeds dominate. All four 1-seeds make the Final Four. Minimal chaos after day 1.',
              },
              {
                name: 'MODERATE',
                weight: '45%',
                color: 'var(--orange)',
                upsets: '9-2-1-1-0',
                total: 13,
                desc: '2024-like. Chaotic R64, a couple Cinderellas survive to S16/E8, but top seeds own the Final Four.',
              },
              {
                name: 'CHAOS',
                weight: '20%',
                color: 'var(--red-dead)',
                upsets: '10-4-2-1-1',
                total: 18,
                desc: '2021-like. Correlated upset chains. Multiple Cinderella runs. A double-digit seed reaches Final Four.',
              },
            ].map((shape) => (
              <Reveal key={shape.name} delay={0.05}>
                <div
                  className="rounded-xl p-5 h-full flex flex-col"
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderTopColor: shape.color,
                    borderTopWidth: 3,
                  }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-display text-lg tracking-wider" style={{ color: shape.color }}>
                      {shape.name}
                    </span>
                    <span className="font-mono text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)' }}>
                      {shape.weight}
                    </span>
                  </div>
                  <p className="font-mono text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                    R64-R32-S16-E8-F4: {shape.upsets}
                  </p>
                  <p className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
                    Total upsets: {shape.total}
                  </p>
                  <p className="text-xs leading-relaxed mt-auto" style={{ color: 'var(--text-secondary)' }}>
                    {shape.desc}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>

          <CalloutCard accent="var(--orange)" icon="🏀" title="The 2026 Talent Thesis">
            NIL money and the transfer portal have concentrated elite talent at the top programs
            more than ever. This means R64 stays chaotic — mid-majors can still punch once —
            but from the Round of 32 onward, the talent wall comes down hard. We expect a
            2024-shaped tournament: ~9 first-round upsets, then chalk. Our decay multipliers
            are steeper than historical averages to reflect this structural shift.
          </CalloutCard>

          <Reveal delay={0.1}>
            <Prose>
              <p>
                The bimodal nature of the R32 is particularly interesting: in 2021 and 2022, there
                were 5 upsets each (chaos years with correlated upset chains). But in 2024 and 2025,
                just 1 each. There's no "average" — it's either a flood or a trickle. Our three-shape
                model captures this reality better than a single target number ever could.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 10. Contrarian Edge ── */}
        <section id="contrarian">
          <SectionHeading number={11} title="THE CONTRARIAN EDGE" subtitle="Game theory meets bracket pools" />
          <Reveal>
            <Prose>
              <p>
                This is the most important strategic concept in the entire project.
                A bracket pool is not a prediction contest — it's a <strong style={{ color: 'var(--orange)' }}>game theory problem</strong>.
                You're not playing against the tournament. You're playing against
                the other people in your pool.
              </p>
            </Prose>
          </Reveal>

          <MathBlock label="The Fundamental Equation">
{`Expected Value(pick) = P(correct) / Public_ownership%

"How likely is this outcome?"  divided by  "How many people picked it?"

Higher P(correct) is good.
Lower ownership% is good.
The ratio is what matters.`}
          </MathBlock>

          <DataTable
            headers={['Champion Pick', 'P(winning title)', 'Public Pick %', 'EV = P / Ownership']}
            rows={[
              ['Duke', '24.1%', '~40%', '0.60 — overvalued'],
              ['Michigan', '22.7%', '~25%', '0.91 — fair value'],
              ['Florida', '12.5%', '~5%', '2.50 — undervalued'],
              ['Michigan State', '~4%', '~1%', '4.00 — high EV moon shot'],
            ]}
          />

          <Reveal delay={0.1}>
            <Prose>
              <p>
                Duke is the most likely champion, but it's a <strong style={{ color: 'var(--red-dead)' }}>bad pick</strong> for
                pool strategy because too many people take them. Florida, at 12.5%
                odds with only 5% ownership, is <strong style={{ color: 'var(--green-alive)' }}>four times more valuable</strong> per bracket.
              </p>
              <p>
                This is why we generate different brackets with different champions.
                Some pick Duke (it's still possible). More pick Florida, Houston,
                Michigan State. A few moon shots pick UConn or Illinois. We allocate
                like an investment portfolio.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 11. Agent Architecture ── */}
        <section id="agents">
          <SectionHeading number={12} title="AGENT ARCHITECTURE" subtitle="An AI team building this together" />
          <Reveal>
            <Prose>
              <p>
                This project isn't built by a single person or a single AI.
                It's built by a <strong style={{ color: 'var(--text-primary)' }}>team of specialized AI agents</strong>,
                each with a defined role, expertise, and set of tools. They
                collaborate, debate, and cross-check each other's work — the
                same way a real research team would operate.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-8">
              <AgentCard
                emoji="📊"
                name="Math Agent"
                role="Sampling algorithms, probability theory, statistical validation. Designed the stratified importance sampling architecture and the enumeration breakthrough."
                tools={['NumPy', 'Probability', 'Calibration']}
              />
              <AgentCard
                emoji="📈"
                name="Stats Agent"
                role="Power index computation, KenPom/Torvik analysis, historical seed upset rates, Brier score calibration."
                tools={['KenPom', 'Torvik', 'AdjEM']}
              />
              <AgentCard
                emoji="💰"
                name="Betting Agent"
                role="Vegas odds integration, de-vig methodology, sharp money signals, line movement analysis."
                tools={['Odds API', 'De-vig', 'Lines']}
              />
              <AgentCard
                emoji="🏀"
                name="Research Agent"
                role="Team scouting, injury reports, coaching records, conference tournament results, Reddit/YouTube sentiment."
                tools={['ESPN', 'Reddit', 'YouTube']}
              />
              <AgentCard
                emoji="🧬"
                name="Biology Agent"
                role="Evolutionary bracket optimization, genetic algorithms, mutation operators. Models brackets as organisms evolving toward fitness."
                tools={['Genetic Algo', 'Mutation', 'Fitness']}
              />
              <AgentCard
                emoji="🏗️"
                name="Lead SWE"
                role="Code review, performance optimization, memory management. Ensures the simulation runs efficiently at scale."
                tools={['Python', 'NumPy', 'PostgreSQL']}
              />
              <AgentCard
                emoji="📋"
                name="Program Manager"
                role="Sprint tracking, quality gates, cross-agent coordination. Ensures deadlines are met and agents don't conflict."
                tools={['Status', 'Decisions', 'Timeline']}
              />
              <AgentCard
                emoji="🎨"
                name="Design Agent"
                role="UI/UX for the live tracker dashboard. Dark theme, real-time bracket visualization, survival charts."
                tools={['React', 'Tailwind', 'Recharts']}
              />
            </div>
          </Reveal>

          <Reveal delay={0.15}>
            <Prose>
              <p>
                The agents operate in parallel — the Math Agent designs the algorithms
                while the Research Agent gathers data, while the Lead SWE builds the
                infrastructure. When they disagree (and they do), we run structured
                debates. The Math Agent proposed full Monte Carlo; the Stats Agent
                pointed out the 32,768 enumeration; the Betting Agent validated that
                FiveThirtyEight uses the same exact-computation approach.
              </p>
              <p>
                This multi-agent architecture isn't just for efficiency — it's for
                <strong style={{ color: 'var(--text-primary)' }}> intellectual diversity</strong>. Different agents catch
                different blind spots. The result is more robust than any single
                perspective could produce.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 12. Research Pipeline ── */}
        <section id="research">
          <SectionHeading number={13} title="RESEARCH PIPELINE" subtitle="Where the data comes from" />
          <Reveal>
            <Prose>
              <p>
                Our probability engine is only as good as the data feeding it.
                We collect from seven primary sources, each contributing a
                different signal to the blend:
              </p>
            </Prose>
          </Reveal>

          <DataTable
            headers={['Source', 'Signal', 'Weight in Blend', 'Update Frequency']}
            rows={[
              ['Vegas spreads', 'Game-specific P_market', '55% (R64)', 'Daily through tipoff'],
              ['KenPom', 'AdjEM, AdjO, AdjD', '25% via P_stats', 'Daily'],
              ['Bart Torvik', 'T-Rank, WAB', 'Cross-check KenPom', 'Daily'],
              ['ESPN BPI', 'Power index', 'Ensemble member', 'Weekly'],
              ['Injury reports', 'Player availability', 'Hard point adjustment', 'Real-time'],
              ['Coaching records', 'March win rates', '7% of power index', 'Static (historical)'],
              ['Public pick %', 'ESPN/Yahoo ownership', 'Contrarian EV calc', 'Post-Selection Sunday'],
            ]}
          />

          <CalloutCard accent="var(--green-alive)" icon="🔄" title="Living Data">
            Selection Sunday is March 15. Until then, we update research daily.
            Conference tournaments are happening right now — auto-bids being decided,
            injuries happening, Vegas lines moving. On Selection Sunday, we lock the
            data and generate final brackets. The system is designed for continuous
            refinement up to the last minute.
          </CalloutCard>
        </section>

        <Divider />

        {/* ── 13. Strategies ── */}
        <section id="strategies">
          <SectionHeading number={14} title="11 STRATEGIES" subtitle="Portfolio theory for brackets" />
          <Reveal>
            <Prose>
              <p>
                Instead of generating random brackets, we generate <strong style={{ color: 'var(--text-primary)' }}>206 million targeted brackets</strong> using
                a diversified portfolio strategy. Like an investment portfolio, we spread our
                budget across different "market scenarios" — from chalk favorites to strategic
                upsets to full chaos.
              </p>
              <p>
                Five strategy profiles, each with a different temperature setting that controls
                how much the bracket leans toward favorites vs. upsets:
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.05}>
            <div className="flex gap-2 my-6 items-end">
              <div className="flex-[30] rounded-t-lg" style={{ height: 80, background: 'var(--cyan)', opacity: 0.8 }}>
                <div className="p-2 text-center">
                  <span className="font-display text-sm text-black">CHALK — 30%</span>
                  <span className="block text-[9px] text-black/70 font-mono">Heavy favorites</span>
                </div>
              </div>
              <div className="flex-[35] rounded-t-lg" style={{ height: 80, background: '#64748B', opacity: 0.8 }}>
                <div className="p-2 text-center">
                  <span className="font-display text-sm text-black">STANDARD — 35%</span>
                  <span className="block text-[9px] text-black/70 font-mono">True probabilities</span>
                </div>
              </div>
              <div className="flex-[10] rounded-t-lg" style={{ height: 80, background: '#22C55E', opacity: 0.8 }}>
                <div className="p-2 text-center">
                  <span className="font-display text-[11px] text-black">SMART — 10%</span>
                  <span className="block text-[8px] text-black/70 font-mono">Targeted flips</span>
                </div>
              </div>
              <div className="flex-[15] rounded-t-lg" style={{ height: 80, background: 'var(--orange)', opacity: 0.8 }}>
                <div className="p-2 text-center">
                  <span className="font-display text-sm text-black">CINDERELLA — 15%</span>
                  <span className="block text-[8px] text-black/70 font-mono">1 wild region</span>
                </div>
              </div>
              <div className="flex-[10] rounded-t-lg" style={{ height: 80, background: '#EF4444', opacity: 0.8 }}>
                <div className="p-2 text-center">
                  <span className="font-display text-[11px] text-white">CHAOS — 10%</span>
                  <span className="block text-[8px] text-white/70 font-mono">Max variance</span>
                </div>
              </div>
            </div>
          </Reveal>

          <CalloutCard accent="#22C55E" icon="🎯" title="Smart Upset: The Edge">
            The key innovation. Most bracket pools are either all-chalk or random chaos.
            Our Smart Upset profile stays chalky overall but strategically targets <strong>coin-flip games</strong> —
            the 8v9, 7v10, 5v12, and 6v11 matchups where Vegas spreads are under 5 points
            and upsets happen 35-52% of the time. These are the games where picking the right
            upset separates winners from the field.
          </CalloutCard>

          <DataTable
            headers={['#', 'Strategy', 'Tier', 'Core Idea']}
            rows={[
              ['1', 'Chalk', 'Core', 'Favorites win. All 1-seeds to Final Four. Baseline.'],
              ['2', 'Contrarian Ownership', 'Satellite', 'EV = P(correct) / ownership%. Fade the public.'],
              ['3', 'Injury Alpha', 'Satellite', 'Exploit slow-to-price injuries (Duke, UNC, Texas Tech).'],
              ['4', 'Coaching Pedigree', 'Satellite', 'Boost Izzo, Hurley, Self, Calipari in March.'],
              ['5', 'Correlated Chaos', 'Moon', 'When one upset hits, the whole region goes haywire.'],
              ['6', 'Seed Historical', 'Satellite', 'Exploit 12/5 (35.6%), 11/6 (37%), 10/7 (39%) base rates.'],
              ['7', 'Champion Diversity', 'Core', 'Spread champion picks across seeds 1-6.'],
              ['8', 'Defense First', 'Core', 'Championship teams play top-30 AdjD defense.'],
              ['9', 'Path of Least Resistance', 'Satellite', 'Find regions where injuries create easy roads.'],
              ['10', 'Momentum / Peaking', 'Satellite', 'Teams on 8+ game win streaks entering tournament.'],
              ['11', 'Historical Base Rate', 'Core', 'Polacheck Method: match 40-year base rates. 62.8% 1-seed champs, 8 R64 upsets.'],
            ]}
          />

          <Reveal delay={0.1}>
            <Prose>
              <p>
                Each strategy produces a different probability matrix, which produces
                a different ranking of the 32,768 regional brackets. The Baseline cluster
                uses neutral R64 temperature (probabilities as-is) but warms up in later
                rounds — creating path diversity where it matters most. The Gamble cluster
                runs hot from R64 (tau=1.4), deliberately picking more upsets that cascade
                into completely different R32/S16/E8 matchups. Both clusters get the 6% mutation.
              </p>
              <p>
                The key insight: <strong style={{ color: 'var(--text-primary)' }}>R64 gambles are the variation engine</strong>. A single
                12-over-5 upset in R64 changes every downstream matchup. Gamble brackets that
                survive Day 1 occupy uncharted territory — paths that virtually no public
                bracket explores. That's where the edge lives.
              </p>
            </Prose>
          </Reveal>
        </section>

        <Divider />

        {/* ── 14. What's Next ── */}
        <section id="whats-next">
          <SectionHeading number={15} title="WHAT'S NEXT" subtitle="The road to Selection Sunday" />
          <Reveal>
            <Prose>
              <p>
                Selection Sunday is <strong style={{ color: 'var(--orange)' }}>March 15, 2026</strong>. Until then, we're:
              </p>
              <ul className="list-none space-y-3 mt-4">
                {[
                  'Updating research daily — conference tournaments, injury reports, line movements',
                  'Calibrating the k-factor against historical data (Brier score target: ≤ 0.205)',
                  'Building the live tracker — real-time bracket pruning as games are played',
                  'Testing the genetic algorithm layer — evolutionary bracket optimization',
                  'Exploring the Biology Agent\'s AlphaFold-inspired bracket structure prediction',
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: 'var(--orange)' }} />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-6">
                When the bracket drops, we generate 206 million targeted brackets —
                each one engineered to exploit a specific edge the public is missing.
                A 6% mutation X-factor flips coin-flip games randomly, injecting the
                chaos that makes March Madness unpredictable. The math doesn't guarantee
                we win. But it guarantees we're playing a fundamentally different game
                than everyone filling out one bracket with their gut.
              </p>
            </Prose>
          </Reveal>

          <Reveal delay={0.2}>
            <div
              className="my-12 rounded-xl p-6 sm:p-8 text-center"
              style={{
                background: 'linear-gradient(135deg, rgba(255, 107, 53, 0.08), rgba(0, 212, 255, 0.05))',
                border: '1px solid var(--border-accent)',
              }}
            >
              <span className="font-display text-2xl sm:text-3xl tracking-wide" style={{ color: 'var(--text-primary)' }}>
                206,000,000 brackets × 11 strategies × 6% mutation
              </span>
              <p className="mt-2 font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                Every edge exploited. Every outcome priced. Every coin flip mutated.
              </p>
            </div>
          </Reveal>
        </section>

        {/* ── Footer ── */}
        <Reveal>
          <footer className="py-12 text-center">
            <div className="h-px mb-8" style={{ background: 'linear-gradient(90deg, transparent, var(--border-subtle), transparent)' }} />
            <p className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              Built with Claude AI agents — Math, Stats, Betting, Biology, SWE, Design, PM
            </p>
            <p className="font-mono text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              March Madness Survivor — 2026 NCAA Tournament
            </p>
          </footer>
        </Reveal>

      </article>
    </div>
  )
}
