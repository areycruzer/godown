from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.models import Vendor
from app.tools.normalize import vendor_dedupe_key
from app.tools.profile import fetch_pdp, fetch_profile
from app.tools.reviews import discover_rating_url, fetch_reviews
from app.tools.search_rp import search_suppliers


def enrich_vendor(
    client: httpx.Client,
    supplier_url: str,
    product_url: str | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vendor = dict(base or {})
    vendor["supplierUrl"] = supplier_url or vendor.get("supplierUrl")
    if product_url:
        vendor["productUrl"] = product_url
    profile = fetch_profile(client, vendor.get("supplierUrl") or supplier_url)
    vendor["profile"] = profile
    if vendor.get("productUrl"):
        vendor["pdp"] = fetch_pdp(client, vendor["productUrl"])
    rating_url = discover_rating_url(vendor)
    # also check profile bag
    if not rating_url and isinstance(profile, dict):
        rating_url = discover_rating_url(profile)
    reviews = fetch_reviews(client, rating_url)
    vendor["reviews"] = reviews
    vendor["mode"] = "enriched"
    return vendor


def run_full_pipeline(
    client: httpx.Client,
    settings: Settings,
    query: str,
    city: str | None = None,
    max_results: int = 20,
) -> dict[str, Any]:
    search = search_suppliers(
        client,
        settings,
        query=query,
        city=city,
        max_pages=min(5, settings.max_pages_hard_cap),
        max_results=max_results,
    )
    suppliers = search.get("suppliers") or []
    enriched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in suppliers:
        if len(enriched) >= max_results:
            break
        v = Vendor(**{k: row.get(k) for k in Vendor.model_fields if k in row})
        key = vendor_dedupe_key(v)
        if key in seen:
            continue
        seen.add(key)
        url = row.get("supplierUrl")
        if not url:
            enriched.append(row)
            continue
        try:
            e = enrich_vendor(
                client,
                supplier_url=url,
                product_url=row.get("productUrl"),
                base=row,
            )
            enriched.append(e)
        except Exception as ex:
            row = dict(row)
            row["enrich_error"] = str(ex)
            enriched.append(row)
    return {
        "query": query,
        "city": city,
        "count": len(enriched),
        "search_errors": search.get("errors"),
        "suppliers": enriched,
    }
