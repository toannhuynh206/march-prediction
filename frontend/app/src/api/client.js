/**
 * API client for March Madness Survivor backend.
 * All fetch wrappers for the FastAPI endpoints.
 */

const BASE = '/api'

async function fetchJSON(path, options = {}) {
  const { headers: extraHeaders, ...restOptions } = options
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...extraHeaders },
    ...restOptions,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = body.detail
    // FastAPI validation errors return detail as an array of objects
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
        : `API error ${res.status}`
    throw new Error(message)
  }
  return res.json()
}

/** GET /api/bracket — full tournament bracket with teams + probabilities */
export function fetchBracket() {
  return fetchJSON('/bracket')
}

/** GET /api/brackets — paginated bracket list (cursor-based) */
export function fetchBrackets({ cursor, limit = 50, sort = 'score', status = 'all', champion = '' } = {}) {
  const params = new URLSearchParams()
  if (cursor) params.set('cursor', cursor)
  if (limit !== 50) params.set('limit', String(limit))
  if (sort !== 'score') params.set('sort', sort)
  if (status !== 'all') params.set('status', status)
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

/** GET /api/results — load existing game results (admin) */
export function fetchResults(adminKey) {
  return fetchJSON('/results', {
    headers: { 'X-Admin-Key': adminKey },
  })
}

/** POST /api/results — submit game result (admin) */
export function submitResult(data, adminKey) {
  return fetchJSON('/results', {
    method: 'POST',
    headers: { 'X-Admin-Key': adminKey },
    body: JSON.stringify(data),
  })
}

/** GET /api/game-results — public game results for bracket comparison */
export function fetchGameResults() {
  return fetchJSON('/game-results')
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
