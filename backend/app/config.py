from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SESSIONS = _ROOT / "sessions"

# OpenAI-compatible defaults per provider
_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4.5-flash",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "gemini": {
        # Google OpenAI-compatible endpoint
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM (OpenAI-compatible) ---
    # llm_provider: glm | openai | gemini | custom
    llm_provider: str = "glm"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    # Provider-specific keys (used when LLM_API_KEY is empty)
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_model: str = "glm-4.5-flash"
    openai_api_key: str = ""
    gemini_api_key: str = ""

    proxy_url: str | None = None
    require_india_egress: bool = True

    sessions_dir: str | None = None
    im_ak: str = ""
    im_cookie: str = ""
    use_ak: bool = False

    max_concurrency: int = 8
    request_timeout_s: float = 45.0
    user_agent: str = "Godown-IndiaMART-Agent/1.0"

    max_agent_rounds: int = 8
    max_pages_hard_cap: int = 11

    def resolved_sessions_dir(self) -> Path:
        if self.sessions_dir and self.sessions_dir.strip():
            return Path(self.sessions_dir).expanduser()
        return _DEFAULT_SESSIONS

    def resolved_provider(self) -> str:
        p = (self.llm_provider or "glm").strip().lower()
        if p in ("zhipu", "bigmodel", "zai"):
            return "glm"
        if p in ("google", "google-ai"):
            return "gemini"
        if p in ("glm", "openai", "gemini", "custom"):
            return p
        return "glm"

    def resolved_api_key(self) -> str:
        if self.llm_api_key.strip():
            return self.llm_api_key.strip()
        p = self.resolved_provider()
        if p == "openai":
            return (self.openai_api_key or "").strip()
        if p == "gemini":
            return (self.gemini_api_key or "").strip()
        # glm / custom fall back to GLM_API_KEY
        return (self.glm_api_key or "").strip()

    def resolved_base_url(self) -> str:
        if self.llm_base_url.strip():
            return self.llm_base_url.strip().rstrip("/")
        p = self.resolved_provider()
        if p == "custom":
            raise ValueError("LLM_PROVIDER=custom requires LLM_BASE_URL")
        if p == "glm":
            return (self.glm_base_url or _PROVIDER_DEFAULTS["glm"]["base_url"]).rstrip("/")
        if p in _PROVIDER_DEFAULTS:
            return _PROVIDER_DEFAULTS[p]["base_url"].rstrip("/")
        return (self.glm_base_url or _PROVIDER_DEFAULTS["glm"]["base_url"]).rstrip("/")

    def resolved_model(self) -> str:
        if self.llm_model.strip():
            return self.llm_model.strip()
        p = self.resolved_provider()
        if p == "glm" and self.glm_model.strip():
            return self.glm_model.strip()
        if p in _PROVIDER_DEFAULTS:
            return _PROVIDER_DEFAULTS[p]["model"]
        return self.glm_model.strip() or _PROVIDER_DEFAULTS["glm"]["model"]

    def llm_configured(self) -> bool:
        return bool(self.resolved_api_key())


@lru_cache
def get_settings() -> Settings:
    return Settings()
