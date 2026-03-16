/**
 * API client for March Madness Survivor backend.
 * All fetch wrappers for the FastAPI endpoints.
 */

const BASE = '/api'

async function fetchJSON(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `API error ${res.status}`)
  }
  return res.json()
}

/** GET /api/bracket — full tournament bracket with teams + probabilities */
export function fetchBracket() {
  return fetchJSON('/bracket')
}

/** GET /api/brackets — paginated bracket list (cursor-based) */
export function fetchBrackets({ cursor, limit = 50, sort = 'score', aliveOnly = false, champion = '' } = {}) {
  const params = new URLSearchParams()
  if (cursor) params.set('cursor', cursor)
  if (limit !== 50) params.set('limit', String(limit))
  if (sort !== 'score') params.set('sort', sort)
  if (aliveOnly) params.set('alive_only', 'true')
  if (champion) params.set('champion', champion)
  return fetchJSON(`/brackets?${params}`)
}

/** GET /api/brackets/:id — single bracket detail */
export function fetchBracketDetail(id) {
  return fetchJSON(`/brackets/${id}`)
}

/** GET /api/stats — dashboard statistics */
export function fetchStats() {
  return fetchJSON('/stats')
}

/** GET /api/stats/regions/:region — region survival stats */
export function fetchRegionStats(region) {
  return fetchJSON(`/stats/regions/${region}`)
}

/** POST /api/results — submit game result (admin) */
export function submitResult(data, adminKey) {
  return fetchJSON('/results', {
    method: 'POST',
    headers: { 'X-Admin-Key': adminKey },
    body: JSON.stringify(data),
  })
}

/** GET /api/portfolio — strategy portfolio breakdown */
export function fetchPortfolio() {
  return fetchJSON('/portfolio')
}

/** SSE stream for live updates */
export function connectSSE(onEvent) {
  const source = new EventSource(`${BASE}/events`)
  source.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      onEvent(data)
    } catch {
      // ignore parse errors on keepalive
    }
  }
  source.onerror = () => {
    source.close()
    // Reconnect after 5s
    setTimeout(() => connectSSE(onEvent), 5000)
  }
  return source
}
