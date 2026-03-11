/**
 * Admin panel — dark broadcast aesthetic with glow accents.
 * Submit game results and trigger bracket pruning.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { submitResult } from '../api/client'
import useTournamentStore from '../store/tournamentStore'

const REGIONS = ['South', 'East', 'West', 'Midwest']
const ROUNDS = ['R64', 'R32', 'S16', 'E8', 'F4', 'Championship']

const inputStyle = {
  backgroundColor: 'var(--bg-card)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-subtle)',
}

const labelStyle = {
  color: 'var(--text-muted)',
}

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
      setStatusMsg({
        type: 'success',
        text: `Result recorded. ${result.eliminated?.toLocaleString() || 0} brackets eliminated, ${result.alive_remaining?.toLocaleString() || 0} remaining.`,
      })
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
    <div className="max-w-xl mx-auto space-y-5">
      {/* Header */}
      <div className="text-center">
        <h2 className="font-display text-3xl tracking-wider" style={{ color: 'var(--orange)' }}>
          ADMIN PANEL
        </h2>
        <p className="text-xs font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
          SUBMIT GAME RESULTS · TRIGGER BRACKET PRUNING
        </p>
      </div>

      {/* Admin key */}
      <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border-subtle)' }}>
        <label className="text-[10px] font-mono uppercase tracking-[0.2em] block mb-2" style={labelStyle}>
          Admin Key
        </label>
        <input
          type="password"
          value={adminKey}
          onChange={(e) => setAdminKey(e.target.value)}
          placeholder="Enter admin key..."
          className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200 focus:ring-1"
          style={{
            ...inputStyle,
            '--tw-ring-color': 'var(--orange)',
          }}
        />
        <p className="text-[10px] font-mono mt-2" style={{ color: 'var(--text-muted)' }}>
          Stored in localStorage. Required for all admin actions.
        </p>
      </div>

      {/* Result entry form */}
      <form
        onSubmit={handleSubmit}
        className="glass rounded-xl p-5 space-y-4"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <h3 className="font-display text-lg tracking-wider" style={{ color: 'var(--text-primary)' }}>
          SUBMIT GAME RESULT
        </h3>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest block mb-1.5" style={labelStyle}>
              Region
            </label>
            <select
              value={form.region}
              onChange={(e) => updateField('region', e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none cursor-pointer"
              style={inputStyle}
            >
              {REGIONS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest block mb-1.5" style={labelStyle}>
              Round
            </label>
            <select
              value={form.round}
              onChange={(e) => updateField('round', e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none cursor-pointer"
              style={inputStyle}
            >
              {ROUNDS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="text-[10px] font-mono uppercase tracking-widest block mb-1.5" style={labelStyle}>
            Game Number
          </label>
          <input
            type="number"
            min="1"
            max="8"
            value={form.game_number}
            onChange={(e) => updateField('game_number', e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={inputStyle}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest block mb-1.5" style={labelStyle}>
              Winner Seed
            </label>
            <input
              type="number"
              min="1"
              max="16"
              value={form.winner_seed}
              onChange={(e) => updateField('winner_seed', e.target.value)}
              placeholder="e.g. 1"
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={inputStyle}
            />
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest block mb-1.5" style={labelStyle}>
              Loser Seed
            </label>
            <input
              type="number"
              min="1"
              max="16"
              value={form.loser_seed}
              onChange={(e) => updateField('loser_seed', e.target.value)}
              placeholder="e.g. 16"
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={inputStyle}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full py-3 rounded-lg font-display text-lg tracking-wider transition-all duration-200 disabled:opacity-50"
          style={{
            backgroundColor: 'var(--orange)',
            color: 'white',
            boxShadow: '0 0 30px rgba(255, 107, 53, 0.2)',
          }}
        >
          {mutation.isPending ? 'SUBMITTING...' : 'SUBMIT RESULT'}
        </button>

        {statusMsg && (
          <div
            className="text-sm p-4 rounded-lg font-mono"
            style={{
              color: statusMsg.type === 'success' ? 'var(--green-alive)' : 'var(--red-dead)',
              background: statusMsg.type === 'success' ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
              border: `1px solid ${statusMsg.type === 'success' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
            }}
          >
            {statusMsg.text}
          </div>
        )}
      </form>

      {/* Instructions */}
      <div
        className="glass rounded-xl p-5 space-y-2"
        style={{ border: '1px solid var(--border-subtle)' }}
      >
        <h4 className="font-display text-base tracking-wider" style={{ color: 'var(--cyan)' }}>
          HOW IT WORKS
        </h4>
        <div className="space-y-1.5 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>01</span>
            Enter the game result with region, round, game number, and seeds.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>02</span>
            The system determines if this was an upset based on seed matchup.
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>03</span>
            All brackets with the wrong pick are eliminated (pruned).
          </p>
          <p className="flex gap-2">
            <span className="font-mono font-bold" style={{ color: 'var(--orange)' }}>04</span>
            Stats and bracket counts update in real-time via SSE.
          </p>
        </div>
      </div>
    </div>
  )
}
