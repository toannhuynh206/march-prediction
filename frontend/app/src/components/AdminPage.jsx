/**
 * Admin panel: submit game results and trigger bracket pruning.
 * Requires X-Admin-Key header for all mutations.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { submitResult } from '../api/client'
import useTournamentStore from '../store/tournamentStore'

const REGIONS = ['South', 'East', 'West', 'Midwest']
const ROUNDS = ['R64', 'R32', 'S16', 'E8', 'F4', 'Championship']

export default function AdminPage() {
  const { adminKey, setAdminKey } = useTournamentStore()
  const queryClient = useQueryClient()

  const [form, setForm] = useState({
    region: 'South',
    round: 'R64',
    game_number: 1,
    winner_seed: '',
    loser_seed: '',
  })
  const [statusMsg, setStatusMsg] = useState(null)

  const mutation = useMutation({
    mutationFn: (data) => submitResult(data, adminKey),
    onSuccess: (result) => {
      setStatusMsg({ type: 'success', text: `Result recorded. ${result.eliminated?.toLocaleString() || 0} brackets eliminated, ${result.alive_remaining?.toLocaleString() || 0} remaining.` })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['brackets'] })
      queryClient.invalidateQueries({ queryKey: ['bracket'] })
    },
    onError: (err) => {
      setStatusMsg({ type: 'error', text: err.message })
    },
  })

  const updateField = (field, value) => {
    setForm({ ...form, [field]: value })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setStatusMsg(null)

    if (!adminKey.trim()) {
      setStatusMsg({ type: 'error', text: 'Admin key is required.' })
      return
    }

    const winnerSeed = parseInt(form.winner_seed, 10)
    const loserSeed = parseInt(form.loser_seed, 10)

    if (isNaN(winnerSeed) || isNaN(loserSeed)) {
      setStatusMsg({ type: 'error', text: 'Winner and loser seeds must be numbers.' })
      return
    }

    mutation.mutate({
      region: form.region,
      round: form.round,
      game_number: parseInt(form.game_number, 10),
      winner_seed: winnerSeed,
      loser_seed: loserSeed,
    })
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      {/* Admin key */}
      <div className="bg-white rounded-lg shadow-sm p-4">
        <label className="text-[11px] font-bold uppercase tracking-wider text-gray-400 block mb-1">
          Admin Key
        </label>
        <input
          type="password"
          value={adminKey}
          onChange={(e) => setAdminKey(e.target.value)}
          placeholder="Enter admin key..."
          className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <p className="text-[10px] text-gray-400 mt-1">Stored in localStorage. Required for all admin actions.</p>
      </div>

      {/* Result entry form */}
      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-4 space-y-3">
        <h3 className="text-[13px] font-bold uppercase tracking-wider" style={{ color: 'var(--midnight)' }}>
          Submit Game Result
        </h3>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-gray-500 block mb-1">Region</label>
            <select
              value={form.region}
              onChange={(e) => updateField('region', e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            >
              {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-gray-500 block mb-1">Round</label>
            <select
              value={form.round}
              onChange={(e) => updateField('round', e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            >
              {ROUNDS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="text-[11px] font-semibold text-gray-500 block mb-1">Game Number</label>
          <input
            type="number"
            min="1"
            max="8"
            value={form.game_number}
            onChange={(e) => updateField('game_number', e.target.value)}
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-gray-500 block mb-1">Winner Seed</label>
            <input
              type="number"
              min="1"
              max="16"
              value={form.winner_seed}
              onChange={(e) => updateField('winner_seed', e.target.value)}
              placeholder="e.g. 1"
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-gray-500 block mb-1">Loser Seed</label>
            <input
              type="number"
              min="1"
              max="16"
              value={form.loser_seed}
              onChange={(e) => updateField('loser_seed', e.target.value)}
              placeholder="e.g. 16"
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full py-2 rounded-lg text-white font-semibold text-sm transition-colors disabled:opacity-50"
          style={{ backgroundColor: 'var(--orange)' }}
        >
          {mutation.isPending ? 'Submitting...' : 'Submit Result'}
        </button>

        {statusMsg && (
          <div className={`text-sm p-3 rounded-lg ${
            statusMsg.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>
            {statusMsg.text}
          </div>
        )}
      </form>

      {/* Instructions */}
      <div className="bg-blue-50 rounded-lg p-4 text-[11px] text-blue-800 space-y-1">
        <p className="font-bold">How it works:</p>
        <p>1. Enter the game result with region, round, game number, and seeds.</p>
        <p>2. The system determines if this was an upset based on seed matchup.</p>
        <p>3. All brackets with the wrong pick are eliminated (pruned).</p>
        <p>4. Stats and bracket counts update in real-time via SSE.</p>
      </div>
    </div>
  )
}
