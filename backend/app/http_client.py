from __future__ import annotations

from pathlib import Path

import httpx

from app.config import Settings


def load_ak_and_cookie(settings: Settings) -> tuple[str, str | None]:
    """Load optional AK + Cookie. Never log values.

    Priority:
      1. IM_AK / IM_COOKIE in .env (paste-ready)
      2. godown/sessions/ak.txt + cookie_header.txt (default folder)
    """
    if not settings.use_ak:
        return "", None

    ak = (settings.im_ak or "").strip()
    cookie = (settings.im_cookie or "").strip() or None

    base = settings.resolved_sessions_dir()
    if not ak:
        ak_path = base / "ak.txt"
        if ak_path.is_file():
            ak = ak_path.read_text(encoding="utf-8").strip()
    if not cookie:
        cookie_path = base / "cookie_header.txt"
        if cookie_path.is_file():
            cookie = cookie_path.read_text(encoding="utf-8").strip() or None

    return ak, cookie


def create_client(settings: Settings) -> httpx.Client:
    headers = {
        "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
        "User-Agent": settings.user_agent,
        "Accept-Language": "en-IN,en;q=0.9,hi-IN;q=0.8",
    }
    ak, cookie = load_ak_and_cookie(settings)
    if cookie:
        headers["Cookie"] = cookie
    # stash ak on client for search params
    client = httpx.Client(
        headers=headers,
        timeout=settings.request_timeout_s,
        proxy=settings.proxy_url or None,
        follow_redirects=True,
    )
    client._godown_ak = ak  # type: ignore[attr-defined]
    return client


def get_ak(client: httpx.Client) -> str:
    return getattr(client, "_godown_ak", "") or ""
