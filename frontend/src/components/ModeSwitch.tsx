import type { Mode } from '../api'

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: 'fast', label: 'Fast', hint: 'Search cards only' },
  { id: 'hybrid', label: 'Hybrid', hint: 'Search + enrich on demand' },
  { id: 'full', label: 'Full', hint: 'Auto enrich vendors' },
]

type Props = {
  mode: Mode
  onChange: (m: Mode) => void
  disabled?: boolean
}

export function ModeSwitch({ mode, onChange, disabled }: Props) {
  return (
    <div className="mode-switch" role="group" aria-label="Enrichment mode">
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          className={mode === m.id ? 'mode-btn active' : 'mode-btn'}
          title={m.hint}
          disabled={disabled}
          onClick={() => onChange(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}
