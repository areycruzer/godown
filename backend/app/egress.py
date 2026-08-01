from __future__ import annotations

import httpx

from app.models import EgressInfo


def check_egress(client: httpx.Client, require_india: bool = True) -> EgressInfo:
    try:
        r = client.get("https://ipapi.co/json/")
        r.raise_for_status()
        data = r.json()
        code = data.get("country_code") or data.get("country")
        info = EgressInfo(
            country_code=code,
            country=data.get("country_name") or data.get("country"),
            ip=data.get("ip"),
            org=data.get("org"),
            ok=(code == "IN") if require_india else True,
            error=None
            if (not require_india or code == "IN")
            else "geo_blocked: egress is not India; set PROXY_URL to an IN proxy or run from India",
        )
        return info
    except Exception as e:
        return EgressInfo(
            ok=False,
            error=f"egress_check_failed: {e}",
        )
