import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BracketView from './components/BracketView'
import ExplorerPage from './components/ExplorerPage'
import StatsPage from './components/StatsPage'
import AdminPage from './components/AdminPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30000,
      staleTime: 10000,
    },
  },
})

const TABS = ['Bracket', 'Explorer', 'Statistics', 'Admin']

const TAB_COMPONENTS = {
  Bracket: BracketView,
  Explorer: ExplorerPage,
  Statistics: StatsPage,
  Admin: AdminPage,
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Bracket')
  const ActiveComponent = TAB_COMPONENTS[activeTab]

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen" style={{ backgroundColor: 'var(--cream)' }}>
        {/* Hero */}
        <header className="text-white text-center py-8" style={{ background: 'linear-gradient(135deg, var(--midnight) 0%, #2C4F7C 100%)' }}>
          <h1 className="text-3xl font-bold tracking-tight">March Madness Survivor</h1>
          <p className="text-lg opacity-80 mt-1">10 Million Bracket Challenge</p>
        </header>

        {/* Tabs */}
        <nav className="flex justify-center gap-1 py-3 px-4" style={{ backgroundColor: 'var(--light-gray)' }}>
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-2 rounded-lg font-semibold text-sm transition-colors ${
                activeTab === tab
                  ? 'text-white'
                  : 'text-gray-600 hover:text-gray-900 bg-white/50'
              }`}
              style={activeTab === tab ? { backgroundColor: 'var(--midnight)' } : {}}
            >
              {tab}
            </button>
          ))}
        </nav>

        {/* Content */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          <ActiveComponent />
        </main>
      </div>
    </QueryClientProvider>
  )
}
