import { useCallback, useEffect, useState } from 'react'
import {
  fetchHealth,
  postChat,
  type ChatMessage,
  type HealthResponse,
  type Mode,
  type Vendor,
} from './api'
import { Chat, type UiMessage } from './components/Chat'
import { EgressBadge } from './components/EgressBadge'
import { ModeSwitch } from './components/ModeSwitch'
import { VendorPanel } from './components/VendorPanel'
import './App.css'

export default function App() {
  const [mode, setMode] = useState<Mode>('hybrid')
  const [city, setCity] = useState('')
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)

  const refreshHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      const h = await fetchHealth()
      setHealth(h)
    } catch {
      setHealth(null)
    } finally {
      setHealthLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshHealth()
    const id = window.setInterval(() => void refreshHealth(), 60_000)
    return () => window.clearInterval(id)
  }, [refreshHealth])

  async function onSend(text: string) {
    const nextHistory: ChatMessage[] = [...history, { role: 'user', content: text }]
    setMessages((m) => [...m, { role: 'user', content: text }])
    setHistory(nextHistory)
    setBusy(true)
    try {
      const res = await postChat({
        messages: nextHistory,
        mode,
        maxResults: 20,
        city: city.trim() || null,
      })
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: res.message,
          traces: res.tool_traces,
        },
      ])
      setHistory((h) => [...h, { role: 'assistant', content: res.message }])
      if (res.vendors?.length) {
        setVendors(res.vendors)
      }
      if (res.egress) {
        setHealth((prev) =>
          prev
            ? { ...prev, egress: res.egress! }
            : {
                status: 'ok',
                egress: res.egress!,
                search_probe: {},
                glm_configured: true,
              },
        )
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${msg}` }])
    } finally {
      setBusy(false)
    }
  }

  function onClear() {
    setMessages([])
    setHistory([])
    setVendors([])
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand-block">
          <h1 className="brand">Godown</h1>
          <p className="tagline">IndiaMART supplier research agent</p>
        </div>
        <ModeSwitch mode={mode} onChange={setMode} disabled={busy} />
        <EgressBadge health={health} loading={healthLoading} />
      </header>

      <div className="controls">
        <label>
          City filter
          <input
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="e.g. Mumbai (optional)"
            disabled={busy}
          />
        </label>
        <button type="button" className="ghost" onClick={() => void refreshHealth()} disabled={busy}>
          Refresh status
        </button>
      </div>

      <main className="workspace">
        <Chat messages={messages} busy={busy} onSend={onSend} onClear={onClear} />
        <VendorPanel vendors={vendors} />
      </main>
    </div>
  )
}
