import { useState, useEffect, useCallback } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BracketView from './components/BracketView'
import ExplorerPage from './components/ExplorerPage'
import StatsPage from './components/StatsPage'
import AdminPage from './components/AdminPage'
import BlogPage from './components/BlogPage'
import PortfolioPage from './components/PortfolioPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30000,
      staleTime: 10000,
    },
  },
})

// Admin tab hidden from public nav — accessible via Ctrl+Shift+A
const TABS = [
  { id: 'Bracket', label: 'BRACKET', icon: '🏀' },
  { id: 'Explorer', label: 'EXPLORER', icon: '🔍' },
  { id: 'Statistics', label: 'STATS', icon: '📊' },
  { id: 'Portfolio', label: 'PORTFOLIO', icon: '💼' },
  { id: 'Blog', label: 'BLOG', icon: '📝' },
]

const TAB_COMPONENTS = {
  Bracket: BracketView,
  Explorer: ExplorerPage,
  Statistics: StatsPage,
  Portfolio: PortfolioPage,
  Admin: AdminPage,
  Blog: BlogPage,
}

function LiveIndicator() {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const timer = setInterval(() => setVisible((v) => !v), 1500)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="flex items-center gap-2 text-xs font-mono" style={{ color: 'var(--green-alive)' }}>
      <span
        className="w-2 h-2 rounded-full"
        style={{
          backgroundColor: 'var(--green-alive)',
          opacity: visible ? 1 : 0.3,
          transition: 'opacity 0.5s',
          boxShadow: visible ? '0 0 8px rgba(34, 197, 94, 0.6)' : 'none',
        }}
      />
      LIVE
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Bracket')
  const ActiveComponent = TAB_COMPONENTS[activeTab]

  // Secret keyboard shortcut: Ctrl+Shift+A opens Admin panel
  const handleKeyDown = useCallback((e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'A') {
      e.preventDefault()
      setActiveTab('Admin')
    }
  }, [])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-deep)' }}>
        {/* ── Hero Header ── */}
        <header className="animated-gradient relative overflow-hidden">
          {/* Court line decorations */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] rounded-full border border-white/[0.03]" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full border border-white/[0.02]" />
            <div className="absolute top-0 left-0 w-full h-[1px]" style={{ background: 'linear-gradient(90deg, transparent, var(--orange), transparent)' }} />
          </div>

          <div className="relative z-10 text-center py-6 sm:py-10 px-4">
            <div className="flex items-center justify-center gap-3 mb-2">
              <div className="h-[1px] w-16" style={{ background: 'linear-gradient(90deg, transparent, var(--orange))' }} />
              <span className="text-xs font-mono tracking-[0.3em] uppercase" style={{ color: 'var(--orange)' }}>
                2025 NCAA Tournament
              </span>
              <div className="h-[1px] w-16" style={{ background: 'linear-gradient(270deg, transparent, var(--orange))' }} />
            </div>

            <h1 className="font-display text-4xl sm:text-5xl md:text-7xl tracking-wide" style={{ color: 'var(--text-primary)' }}>
              MARCH MADNESS
              <span className="block text-2xl sm:text-3xl md:text-4xl mt-1" style={{ color: 'var(--orange)' }}>
                SURVIVOR
              </span>
            </h1>

            <div className="flex items-center justify-center gap-3 sm:gap-4 mt-3 sm:mt-4">
              <span
                className="font-mono text-xs sm:text-sm tracking-wider px-3 sm:px-4 py-1 rounded-full"
                style={{
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-subtle)',
                  background: 'rgba(255,255,255,0.03)',
                }}
              >
                206,000,000 BRACKETS
              </span>
              <LiveIndicator />
            </div>
          </div>

          {/* Bottom edge glow */}
          <div className="h-[2px]" style={{ background: 'linear-gradient(90deg, transparent, var(--orange), var(--cyan), transparent)' }} />
        </header>

        {/* ── Tab Navigation ── */}
        <nav
          className="sticky top-0 z-50 px-4 py-2 flex justify-center gap-1"
          style={{
            backgroundColor: 'rgba(11, 14, 23, 0.85)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="px-3 sm:px-5 py-2.5 rounded-lg font-semibold text-sm transition-all duration-200 flex items-center gap-1.5 sm:gap-2"
                style={{
                  color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                  backgroundColor: isActive ? 'var(--bg-card)' : 'transparent',
                  border: isActive ? '1px solid var(--border-accent)' : '1px solid transparent',
                  boxShadow: isActive ? '0 0 20px rgba(255, 107, 53, 0.08)' : 'none',
                }}
              >
                <span className="text-base">{tab.icon}</span>
                <span className="tracking-wider hidden sm:inline">{tab.label}</span>
              </button>
            )
          })}
        </nav>

        {/* ── Content ── */}
        <main className="max-w-7xl mx-auto px-2 sm:px-4 py-4 sm:py-6">
          <ActiveComponent />
        </main>

        {/* ── Footer ── */}
        <footer className="text-center py-6 px-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            MARCH MADNESS SURVIVOR — STRATIFIED IMPORTANCE SAMPLING — 206M BRACKETS
          </p>
        </footer>
      </div>
    </QueryClientProvider>
  )
}
