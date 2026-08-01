from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import run_agent_chat
from app.config import get_settings
from app.egress import check_egress
from app.http_client import create_client
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.tools.search_rp import fetch_search_page

app = FastAPI(title="Godown IndiaMART Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    client = create_client(settings)
    try:
        egress = check_egress(client, settings.require_india_egress)
        probe: dict = {"ok": False}
        if egress.ok or not settings.require_india_egress:
            status, data, err = fetch_search_page(client, "steel pipe", 1)
            probe = {
                "ok": status == 200 and data is not None,
                "status": status,
                "error": err,
                "bytes": None,
            }
            if data is not None:
                import orjson

                probe["bytes"] = len(orjson.dumps(data))
        else:
            probe = {"ok": False, "skipped": True, "reason": "egress_not_in"}
        configured = settings.llm_configured()
        return HealthResponse(
            status="ok" if egress.ok or not settings.require_india_egress else "degraded",
            egress=egress,
            search_probe=probe,
            llm_configured=configured,
            llm_provider=settings.resolved_provider(),
            llm_model=settings.resolved_model() if configured else None,
            glm_configured=configured,
        )
    finally:
        client.close()


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    settings = get_settings()
    return run_agent_chat(
        settings=settings,
        messages=body.messages,
        mode=body.mode,
        max_results=body.maxResults,
        city=body.city,
    )
