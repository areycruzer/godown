export type Mode = 'fast' | 'hybrid' | 'full'

export type ChatMessage = {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export type ToolTrace = {
  name: string
  arguments: Record<string, unknown>
  result_preview: string
  ok: boolean
}

export type Vendor = {
  mode?: string
  productName?: string | null
  companyName?: string | null
  supplierCity?: string | null
  supplierState?: string | null
  price?: string | null
  currency?: string | null
  moq?: string | null
  phone?: string | null
  gstNumber?: string | null
  supplierId?: string | null
  productUrl?: string | null
  supplierUrl?: string | null
  imageUrl?: string | null
  supplierRating?: number | null
  ratingCount?: number | null
  profile?: Record<string, unknown> | null
  pdp?: Record<string, unknown> | null
  reviews?: Array<Record<string, unknown>> | null
}

export type EgressInfo = {
  country_code?: string | null
  country?: string | null
  ip?: string | null
  org?: string | null
  ok: boolean
  error?: string | null
}

export type ChatResponse = {
  message: string
  tool_traces: ToolTrace[]
  vendors: Vendor[]
  egress?: EgressInfo | null
  error?: string | null
}

export type HealthResponse = {
  status: string
  egress: EgressInfo
  search_probe: Record<string, unknown>
  glm_configured: boolean
}

export async function fetchHealth(): Promise<HealthResponse> {
  const r = await fetch('/api/health')
  if (!r.ok) throw new Error(`health ${r.status}`)
  return r.json()
}

export async function postChat(body: {
  messages: ChatMessage[]
  mode: Mode
  maxResults?: number
  city?: string | null
}): Promise<ChatResponse> {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const text = await r.text()
    throw new Error(text || `chat ${r.status}`)
  }
  return r.json()
}
