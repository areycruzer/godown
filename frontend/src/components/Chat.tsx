import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChatMessage, ToolTrace } from '../api'
import { ToolTraceList } from './ToolTrace'

type UiMessage = {
  role: 'user' | 'assistant'
  content: string
  traces?: ToolTrace[]
}

type Props = {
  messages: UiMessage[]
  busy: boolean
  onSend: (text: string) => void
  onClear: () => void
}

export function Chat({ messages, busy, onSend, onClear }: Props) {
  const [text, setText] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  function submit(e: FormEvent) {
    e.preventDefault()
    const t = text.trim()
    if (!t || busy) return
    setText('')
    onSend(t)
  }

  return (
    <section className="chat">
      <div className="chat-toolbar">
        <h2>Chat</h2>
        <button type="button" className="linkish" onClick={onClear} disabled={busy}>
          Clear
        </button>
      </div>
      <div className="chat-log">
        {messages.length === 0 && (
          <p className="chat-empty">
            Ask for suppliers, e.g. <em>“Find shredders in Coimbatore”</em> or{' '}
            <em>“steel pipe suppliers in Mumbai”</em>.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble bubble-${m.role}`}>
            <div className="bubble-role">{m.role}</div>
            <div className="bubble-body">{m.content}</div>
            {m.traces && m.traces.length > 0 && <ToolTraceList traces={m.traces} />}
          </div>
        ))}
        {busy && <div className="bubble bubble-assistant thinking">Working…</div>}
        <div ref={bottomRef} />
      </div>
      <form className="chat-form" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask Godown to find vendors…"
          disabled={busy}
          aria-label="Message"
        />
        <button type="submit" disabled={busy || !text.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}

export type { UiMessage, ChatMessage }
