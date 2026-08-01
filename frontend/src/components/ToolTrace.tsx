import { useState } from 'react'
import type { ToolTrace } from '../api'

type Props = { traces: ToolTrace[] }

export function ToolTraceList({ traces }: Props) {
  if (!traces.length) return null
  return (
    <div className="tool-traces">
      {traces.map((t, i) => (
        <ToolTraceItem key={`${t.name}-${i}`} trace={t} />
      ))}
    </div>
  )
}

function ToolTraceItem({ trace }: { trace: ToolTrace }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`tool-trace ${trace.ok ? '' : 'tool-fail'}`}>
      <button type="button" className="tool-trace-head" onClick={() => setOpen((v) => !v)}>
        <span className="tool-name">{trace.name}</span>
        <span className="tool-args">{JSON.stringify(trace.arguments)}</span>
        <span className="tool-chevron">{open ? '−' : '+'}</span>
      </button>
      {open && <pre className="tool-body">{trace.result_preview}</pre>}
    </div>
  )
}
