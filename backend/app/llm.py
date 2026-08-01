"""OpenAI-compatible LLM client for glm / openai / gemini / custom."""

from __future__ import annotations

from openai import OpenAI

from app.config import Settings


def create_llm_client(settings: Settings) -> OpenAI:
    key = settings.resolved_api_key()
    if not key:
        raise ValueError(
            "No LLM API key set. Set LLM_API_KEY, or OPENAI_API_KEY / "
            "GEMINI_API_KEY / GLM_API_KEY for the chosen LLM_PROVIDER."
        )
    return OpenAI(
        api_key=key,
        base_url=settings.resolved_base_url(),
    )
