/**
 * Zustand store for March Madness Survivor UI state.
 */

import { create } from 'zustand'

const useTournamentStore = create((set) => ({
  // Active tab
  activeTab: 'Bracket',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // Selected region for region-specific views
  selectedRegion: 'South',
  setSelectedRegion: (region) => set({ selectedRegion: region }),

  // Explorer state
  explorerCursor: null,
  explorerSort: 'probability',
  explorerAliveOnly: false,
  explorerChampion: '',
  setExplorerCursor: (cursor) => set({ explorerCursor: cursor }),
  setExplorerSort: (sort) => set({ explorerSort: sort, explorerCursor: null }),
  setExplorerAliveOnly: (val) => set({ explorerAliveOnly: val, explorerCursor: null }),
  setExplorerChampion: (team) => set({ explorerChampion: team, explorerCursor: null }),

  // Bracket viewer state
  bracketSort: 'probability',
  bracketChampion: '',
  setBracketSort: (sort) => set({ bracketSort: sort }),
  setBracketChampion: (team) => set({ bracketChampion: team }),

  // Expanded bracket in explorer
  expandedBracketId: null,
  setExpandedBracketId: (id) =>
    set((state) => ({
      expandedBracketId: state.expandedBracketId === id ? null : id,
    })),

  // Admin state
  adminKey: localStorage.getItem('adminKey') || '',
  setAdminKey: (key) => {
    localStorage.setItem('adminKey', key)
    set({ adminKey: key })
  },

  // SSE connection status
  sseConnected: false,
  setSseConnected: (val) => set({ sseConnected: val }),

  // Last pruning event
  lastPruneEvent: null,
  setLastPruneEvent: (event) => set({ lastPruneEvent: event }),
}))

export default useTournamentStore
