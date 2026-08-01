from __future__ import annotations

import random
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.config import Settings
from app.http_client import get_ak
from app.models import Vendor
from app.tools.normalize import fields_to_vendor, vendor_dedupe_key

SEARCH_API = "https://dir.indiamart.com/api/search.rp"
SEARCH_HTML = "https://dir.indiamart.com/search.mp"


def iter_fields(data: dict[str, Any]):
    results = data.get("results") or data.get("data") or []
    if isinstance(results, dict):
        results = results.get("results") or results.get("docs") or []
    for item in results or []:
        if isinstance(item, dict) and isinstance(item.get("fields"), dict):
            yield item["fields"]
        elif isinstance(item, dict):
            yield item


def fetch_search_page(
    client: httpx.Client,
    q: str,
    page: int,
    city: str | None = None,
) -> tuple[int, dict | None, str | None]:
    # Note: do NOT pass cq= to search.rp — live tests show cq corrupts rankings
    # (e.g. cq=Delhi returns stainless-steel cards). City is filtered client-side.
    params: dict[str, Any] = {
        "q": q,
        "page": page,
        "source": "dir.search",
        "AK": get_ak(client),
    }
    _ = city
    try:
        r = client.get(SEARCH_API, params=params)
        if r.status_code in (401, 402) and get_ak(client):
            client._godown_ak = ""  # type: ignore[attr-defined]
            params["AK"] = ""
            r = client.get(SEARCH_API, params=params)
        if r.status_code == 200:
            try:
                return r.status_code, r.json(), None
            except Exception:
                return r.status_code, None, "json_parse_error"
        return r.status_code, None, r.text[:200]
    except Exception as e:
        return 0, None, str(e)


def _extract_initial_state(html: str) -> dict | None:
    import json
    import re

    m = re.search(
        r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;?\s*</script>",
        html,
        re.DOTALL,
    )
    if not m:
        m = re.search(r"__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;", html, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            return json.loads(raw[: raw.rfind("}") + 1])
        except Exception:
            return None


def _walk_cards(obj: Any, out: list[dict]) -> None:
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if ("companyname" in keys or "companyName" in keys) and (
            "glusrid" in keys or "original_title" in keys or "title" in keys
        ):
            out.append(obj)
        for v in obj.values():
            _walk_cards(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_cards(v, out)


def fetch_search_html_fallback(
    client: httpx.Client,
    q: str,
    city: str | None = None,
) -> list[Vendor]:
    params = f"ss={quote_plus(q)}"
    if city:
        params += f"&cq={quote_plus(city)}"
    url = f"{SEARCH_HTML}?{params}"
    r = client.get(url)
    if r.status_code != 200:
        return []
    if "export.indiamart.com" in str(r.url):
        return []
    state = _extract_initial_state(r.text)
    if not state:
        return []
    cards: list[dict] = []
    _walk_cards(state, cards)
    vendors = []
    seen = set()
    for c in cards:
        v = fields_to_vendor(c)
        key = vendor_dedupe_key(v)
        if key in seen:
            continue
        seen.add(key)
        vendors.append(v)
    return vendors


def search_suppliers(
    client: httpx.Client,
    settings: Settings,
    query: str,
    city: str | None = None,
    max_pages: int | None = None,
    max_results: int = 50,
) -> dict[str, Any]:
    # City filtering is client-side. Oversample pages when city is set.
    pages = min(max_pages or (8 if city else 3), settings.max_pages_hard_cap)
    rows: list[Vendor] = []
    seen: set[str] = set()
    errors: list[str] = []
    used_fallback = False
    skipped_off_city = 0

    def _ingest_fields(fields_iter) -> None:
        nonlocal skipped_off_city
        for fields in fields_iter:
            if len(rows) >= max_results:
                return
            v = fields_to_vendor(fields)
            if city and not _city_ok(v.supplierCity, v.supplierState, city):
                skipped_off_city += 1
                continue
            key = vendor_dedupe_key(v)
            if key in seen:
                continue
            seen.add(key)
            rows.append(v)

    queries = [query]
    if city and city.lower() not in query.lower():
        queries.append(f"{query} {city}")

    for q in queries:
        if len(rows) >= max_results:
            break
        for page in range(1, pages + 1):
            if len(rows) >= max_results:
                break
            time.sleep(random.uniform(0.15, 0.45))
            status, data, err = fetch_search_page(client, q, page, city)
            if status == 400:
                errors.append(f"soft_cap_{q}_page_{page}")
                break
            if status == 403:
                errors.append("geo_blocked_or_forbidden")
                break
            if status == 429:
                time.sleep(5)
                status, data, err = fetch_search_page(client, q, page, city)
            if status != 200 or not data:
                errors.append(f"page_{page}_status_{status}:{err}")
                if page == 1 and q == query:
                    fb = fetch_search_html_fallback(client, query, city)
                    if fb:
                        used_fallback = True
                        for v in fb:
                            if city and not _city_ok(
                                v.supplierCity, v.supplierState, city
                            ):
                                skipped_off_city += 1
                                continue
                            key = vendor_dedupe_key(v)
                            if key not in seen:
                                seen.add(key)
                                rows.append(v)
                break
            cards = list(iter_fields(data))
            if not cards:
                break
            _ingest_fields(cards)

    return {
        "query": query,
        "city": city,
        "count": len(rows),
        "skipped_off_city": skipped_off_city,
        "used_html_fallback": used_fallback,
        "errors": errors,
        "suppliers": [r.model_dump() for r in rows[:max_results]],
        "city_filter_strict": bool(city),
    }


def _city_ok(supplier_city: str | None, supplier_state: str | None, city: str) -> bool:
    from app.models import Vendor
    from app.present import vendor_matches_city

    return vendor_matches_city(
        Vendor(supplierCity=supplier_city, supplierState=supplier_state),
        city,
    )
