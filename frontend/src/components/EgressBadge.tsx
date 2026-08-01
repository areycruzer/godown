import type { EgressInfo, HealthResponse } from '../api'

type Props = {
  health: HealthResponse | null
  loading?: boolean
}

export function EgressBadge({ health, loading }: Props) {
  if (loading || !health) {
    return <span className="badge badge-muted">Egress…</span>
  }
  const e: EgressInfo = health.egress
  const probeOk = Boolean(health.search_probe?.ok)
  const glm = health.glm_configured
  const cls = e.ok ? 'badge badge-ok' : 'badge badge-bad'
  return (
    <div className="badge-row">
      <span className={cls} title={e.error || e.org || ''}>
        {e.ok ? `IN · ${e.ip ?? 'ok'}` : `Blocked · ${e.country_code ?? '?'}`}
      </span>
      <span className={probeOk ? 'badge badge-ok' : 'badge badge-muted'}>
        search.rp {probeOk ? 'ok' : '—'}
      </span>
      <span className={glm ? 'badge badge-ok' : 'badge badge-bad'}>
        GLM {glm ? 'ready' : 'no key'}
      </span>
    </div>
  )
}
