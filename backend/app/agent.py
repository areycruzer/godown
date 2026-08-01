from __future__ import annotations

import json
from typing import Any

from openai import APIError, APIStatusError, OpenAI

from app.config import Settings
from app.egress import check_egress
from app.http_client import create_client
from app.llm import create_llm_client
from app.models import (
    ChatMessage,
    ChatResponse,
    EgressInfo,
    Mode,
    ToolTrace,
    Vendor,
)
from app.present import extract_city_from_text, present_vendors_for_user, vendor_matches_city
from app.tools.pipeline import enrich_vendor, run_full_pipeline
from app.tools.search_rp import search_suppliers

SYSTEM_PROMPT = """You are Godown, a procurement research assistant for IndiaMART suppliers in India.

## How you work
1. Call tools to fetch real supplier data. Never invent GST, phone, address, prices, ratings, or URLs.
2. Always pass the user's city into tool arguments when a city is mentioned (message or default city).
3. After tools return, a separate results-editor will filter and rewrite the final answer — still, your tool calls must target the right city/query.
4. Do not suggest RFQ / Get Best Price / phone-reveal flows.

## City & relevance (critical)
- If the user asks for a city (e.g. Delhi), you MUST pass that city to search_suppliers / run_full_pipeline.
- IndiaMART often returns nearby or national noise. Prefer exact city matches; for Delhi accept New Delhi / Delhi NCR.
- Never present off-city suppliers as if they satisfy a city request.
- If tools return empty or only wrong-city hits, say so clearly and suggest a nearby city or broader keyword — do not pad with unrelated cities.

## Tool choice by mode
- fast: search_suppliers only
- hybrid: search_suppliers, then enrich_vendor for specific promising storefronts the user cares about
- full: run_full_pipeline for deep enrichment

## Style while calling tools
Keep intermediate chatter minimal. Focus on correct tool arguments (query, city, max_pages).
"""


def _tools_for_mode(mode: Mode) -> list[dict[str, Any]]:
    search_tool = {
        "type": "function",
        "function": {
            "name": "search_suppliers",
            "description": (
                "Search IndiaMART for product/supplier listings. "
                "ALWAYS pass city when the user named a city. "
                "Results are city-filtered server-side when city is set."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product or keyword to search"},
                    "city": {
                        "type": "string",
                        "description": "Indian city filter, e.g. Delhi, Mumbai, Coimbatore. Required if user named a city.",
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Pages to fetch (1-11). Use 4-6 when filtering by city.",
                    },
                },
                "required": ["query"],
            },
        },
    }
    enrich_tool = {
        "type": "function",
        "function": {
            "name": "enrich_vendor",
            "description": "Deep-fetch one supplier: profile KYC fields, optional PDP, and reviews.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_url": {
                        "type": "string",
                        "description": "IndiaMART supplier storefront URL",
                    },
                    "product_url": {
                        "type": "string",
                        "description": "Optional product detail URL",
                    },
                },
                "required": ["supplier_url"],
            },
        },
    }
    full_tool = {
        "type": "function",
        "function": {
            "name": "run_full_pipeline",
            "description": (
                "Search then enrich each unique supplier up to max_results. "
                "Pass city when the user named one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "city": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    }
    if mode == Mode.fast:
        return [search_tool]
    if mode == Mode.hybrid:
        return [search_tool, enrich_tool]
    return [full_tool]


def _preview(obj: Any, limit: int = 1200) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def _collect_vendors(payload: dict[str, Any], bucket: list[Vendor]) -> None:
    rows = payload.get("suppliers")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                try:
                    bucket.append(Vendor.model_validate(row))
                except Exception:
                    pass
    if payload.get("supplierUrl") or payload.get("companyName") or payload.get("profile"):
        if "suppliers" not in payload:
            try:
                bucket.append(Vendor.model_validate(payload))
            except Exception:
                pass


def _resolve_city(messages: list[ChatMessage], city: str | None) -> str | None:
    if city and city.strip():
        return city.strip()
    # last user message wins
    for m in reversed(messages):
        if m.role == "user":
            found = extract_city_from_text(m.content)
            if found:
                return found
    return None


def _latest_user_text(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def run_agent_chat(
    settings: Settings,
    messages: list[ChatMessage],
    mode: Mode,
    max_results: int = 20,
    city: str | None = None,
) -> ChatResponse:
    if not settings.llm_configured():
        return ChatResponse(
            message=(
                "No LLM API key set. In godown/.env set LLM_PROVIDER "
                "(glm|openai|gemini|custom) and LLM_API_KEY — or the matching "
                "GLM_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY — then restart."
            ),
            error="missing_llm_api_key",
        )

    resolved_city = _resolve_city(messages, city)
    client = create_client(settings)
    try:
        egress = check_egress(client, settings.require_india_egress)
        if settings.require_india_egress and not egress.ok:
            return ChatResponse(
                message=(
                    f"IndiaMART access blocked: egress country is "
                    f"{egress.country_code or 'unknown'}. "
                    "Set PROXY_URL to a working India proxy or run from an Indian IP."
                ),
                egress=egress,
                error="geo_blocked",
            )

        llm = create_llm_client(settings)
        tools = _tools_for_mode(mode)

        sys_extra = (
            f"\nCurrent mode: {mode.value}."
            f"\nDefault maxResults: {max_results}."
        )
        if resolved_city:
            sys_extra += (
                f"\nREQUIRED CITY FILTER: {resolved_city}. "
                "Pass this city on every search/pipeline tool call."
            )

        oai_messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT + sys_extra}
        ]
        for m in messages:
            oai_messages.append({"role": m.role, "content": m.content})

        traces: list[ToolTrace] = []
        vendors: list[Vendor] = []

        try:
            return _run_tool_loop(
                llm=llm,
                settings=settings,
                oai_messages=oai_messages,
                tools=tools,
                max_results=max_results,
                city=resolved_city,
                http_client=client,
                egress=egress,
                traces=traces,
                vendors=vendors,
                user_request=_latest_user_text(messages),
            )
        except APIStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("error", {}).get("message") or ""
            except Exception:
                detail = e.message or str(e)
            provider = settings.resolved_provider()
            model = settings.resolved_model()
            return ChatResponse(
                message=(
                    f"LLM API error ({provider}, HTTP {e.status_code}): "
                    f"{detail or e.message}. "
                    f"Check LLM_MODEL / provider key in .env (current model: {model})."
                ),
                egress=egress,
                error="llm_api_error",
            )
        except APIError as e:
            return ChatResponse(
                message=(
                    f"LLM API error ({settings.resolved_provider()}): "
                    f"{e.message or e}"
                ),
                egress=egress,
                error="llm_api_error",
            )
    finally:
        client.close()


def _dedupe(vendors: list[Vendor]) -> list[Vendor]:
    deduped: list[Vendor] = []
    seen: set[str] = set()
    for v in vendors:
        key = v.supplierId or v.supplierUrl or v.productUrl or str(id(v))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(v)
    return deduped


def _run_tool_loop(
    *,
    llm: OpenAI,
    settings: Settings,
    oai_messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_results: int,
    city: str | None,
    http_client,
    egress: EgressInfo,
    traces: list[ToolTrace],
    vendors: list[Vendor],
    user_request: str,
) -> ChatResponse:
    client = http_client
    for _ in range(settings.max_agent_rounds):
        resp = llm.chat.completions.create(
            model=settings.resolved_model(),
            messages=oai_messages,
            tools=tools,
            tool_choice="auto",
        )
        choice = resp.choices[0]
        msg = choice.message

        if msg.tool_calls:
            oai_messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if city and name in ("search_suppliers", "run_full_pipeline"):
                    # Force required city — do not let the model omit/override with blank
                    args["city"] = city
                if name == "run_full_pipeline" and "max_results" not in args:
                    args["max_results"] = max_results
                if name == "search_suppliers" and city and "max_pages" not in args:
                    args["max_pages"] = 6

                ok = True
                try:
                    if name == "search_suppliers":
                        # Oversample then city-filter so panel still fills
                        fetch_cap = max_results * 3 if city else max_results
                        result = search_suppliers(
                            client,
                            settings,
                            query=args.get("query") or "",
                            city=args.get("city"),
                            max_pages=args.get("max_pages"),
                            max_results=fetch_cap,
                        )
                    elif name == "enrich_vendor":
                        result = enrich_vendor(
                            client,
                            supplier_url=args.get("supplier_url") or "",
                            product_url=args.get("product_url"),
                        )
                    elif name == "run_full_pipeline":
                        result = run_full_pipeline(
                            client,
                            settings,
                            query=args.get("query") or "",
                            city=args.get("city"),
                            max_results=int(args.get("max_results") or max_results),
                        )
                    else:
                        result = {"error": f"unknown_tool:{name}"}
                        ok = False
                except Exception as e:
                    result = {"error": str(e)}
                    ok = False

                if isinstance(result, dict):
                    _collect_vendors(result, vendors)
                    if city:
                        vendors[:] = [v for v in vendors if vendor_matches_city(v, city)]

                traces.append(
                    ToolTrace(
                        name=name,
                        arguments=args,
                        result_preview=_preview(result),
                        ok=ok,
                    )
                )
                oai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _preview(result, limit=8000),
                    }
                )
            continue

        # Tool loop done — presentation LLM layer (not raw model dump)
        deduped = _dedupe(vendors)
        if city:
            deduped = [v for v in deduped if vendor_matches_city(v, city)]

        message, shown, present_note = present_vendors_for_user(
            llm,
            settings,
            user_request=user_request,
            city=city,
            vendors=deduped,
            max_results=max_results,
        )
        if present_note:
            traces.append(
                ToolTrace(
                    name="present_results",
                    arguments={"city": city, "raw_count": len(deduped)},
                    result_preview=present_note,
                    ok=True,
                )
            )
        # If model had text but no vendors, still run presenter only when we have data;
        # if no tool data at all, fall back to model text with a caution.
        if not deduped and not shown:
            fallback = msg.content or message
            if city:
                fallback = (
                    f"{fallback}\n\n_Note: required city filter was **{city}**; "
                    "no on-city suppliers were kept._"
                )
            return ChatResponse(
                message=fallback,
                tool_traces=traces,
                vendors=[],
                egress=egress,
            )

        return ChatResponse(
            message=message,
            tool_traces=traces,
            vendors=shown,
            egress=egress,
        )

    deduped = _dedupe(vendors)
    if city:
        deduped = [v for v in deduped if vendor_matches_city(v, city)]
    message, shown, _ = present_vendors_for_user(
        llm,
        settings,
        user_request=user_request,
        city=city,
        vendors=deduped,
        max_results=max_results,
    )
    return ChatResponse(
        message=message or "Stopped after max tool rounds. Try a narrower query.",
        tool_traces=traces,
        vendors=shown,
        egress=egress,
        error="max_rounds",
    )
