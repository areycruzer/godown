# Godown

Chat agent that finds IndiaMART suppliers via LLM tool-calling.

**Stack:** React (Vite) UI · FastAPI backend · Indian IP (or `PROXY_URL`) · any OpenAI-compatible LLM (GLM / OpenAI / Gemini / custom).

## Run

```bash
cp .env.example .env
# set LLM_PROVIDER + API key (see below)

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# new terminal
cd frontend
npm install && npm run dev
```

Open http://127.0.0.1:5173 · Health: `curl -s http://127.0.0.1:8000/api/health`

## LLM providers

Set in `.env` (no UI switch):

| `LLM_PROVIDER` | Key env | Default model | Default base |
|----------------|---------|---------------|--------------|
| `glm` | `GLM_API_KEY` or `LLM_API_KEY` | `glm-4.5-flash` | Zhipu BigModel |
| `openai` | `OPENAI_API_KEY` or `LLM_API_KEY` | `gpt-4o-mini` | `https://api.openai.com/v1` |
| `gemini` | `GEMINI_API_KEY` or `LLM_API_KEY` | `gemini-2.0-flash` | Google OpenAI-compat |
| `custom` | `LLM_API_KEY` | `LLM_MODEL` (required) | `LLM_BASE_URL` (required) |

Optional overrides for any provider: `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`.

Examples:

```bash
# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# LLM_MODEL=gpt-4o

# Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
# LLM_MODEL=gemini-2.0-flash

# Any other OpenAI-compatible API
LLM_PROVIDER=custom
LLM_API_KEY=...
LLM_MODEL=...
LLM_BASE_URL=https://your-host/v1
```

Restart the backend after changing provider/key.

## Modes

| Mode | Behavior |
|------|----------|
| Fast | Search only |
| Hybrid | Search + enrich one vendor |
| Full | Search + profile / PDP / reviews (slower) |

Set a **City** in the UI header, or say “in Delhi” in the prompt.

## Web Search (RAG via MCP)

The agent supports RAG-based Web Search through Exa's MCP server to enrich supplier data, review information, and product details.
To use this feature:
1. Ensure Node.js (`npx`) is installed on the backend host.
2. Add your Exa API key in `.env`:
   ```bash
   EXA_API_KEY=your_exa_api_key_here
   ```

## Optional login (`sessions/`)

Unauthenticated search works. For logged-in cookies (~24h TTL):

1. Paste `ak.txt` + `cookie_header.txt` into `sessions/` (or `IM_AK` / `IM_COOKIE` in `.env`)
2. `USE_AK=true`, restart backend

```bash
python3 scripts/indiamart_login.py --mobile 10DIGIT
```

## Env (other)

| Var | Notes |
|-----|--------|
| `PROXY_URL` | Only if egress is not India |
| `REQUIRE_INDIA_EGRESS` | Default `true` |
| `USE_AK` | `true` when session files are fresh |
| `EXA_API_KEY` | Optional Exa API key for Web Search (RAG via MCP) |


## Layout

```
godown/
├── backend/app/     # FastAPI + IndiaMART tools + LLM agent
├── frontend/src/    # Chat UI
├── sessions/        # local AK/cookie paste (gitignored secrets)
└── scripts/         # indiamart_login.py
```
