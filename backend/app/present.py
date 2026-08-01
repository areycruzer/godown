from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.config import Settings
from app.models import Vendor

# Common IndiaMART / NCR aliases so "Delhi" matches New Delhi, etc.
CITY_ALIASES: dict[str, set[str]] = {
    "delhi": {"delhi", "new delhi", "newdelhi", "delhi ncr", "ncr", "delhi/ncr"},
    "new delhi": {"delhi", "new delhi", "newdelhi", "delhi ncr", "ncr"},
    "mumbai": {"mumbai", "bombay", "navi mumbai", "thane"},
    "bengaluru": {"bengaluru", "bangalore"},
    "bangalore": {"bengaluru", "bangalore"},
    "chennai": {"chennai", "madras"},
    "kolkata": {"kolkata", "calcutta"},
    "gurgaon": {"gurgaon", "gurugram"},
    "gurugram": {"gurgaon", "gurugram"},
    "noida": {"noida", "greater noida"},
}


def normalize_city(city: str | None) -> str:
    return re.sub(r"\s+", " ", (city or "").strip().lower())


def city_match_tokens(city: str | None) -> set[str]:
    c = normalize_city(city)
    if not c:
        return set()
    aliases = set(CITY_ALIASES.get(c, {c}))
    aliases.add(c)
    return aliases


def vendor_matches_city(vendor: Vendor | dict[str, Any], city: str | None) -> bool:
    if not city:
        return True
    tokens = city_match_tokens(city)
    if isinstance(vendor, Vendor):
        loc = " ".join(
            [
                vendor.supplierCity or "",
                vendor.supplierState or "",
            ]
        ).lower()
    else:
        loc = " ".join(
            [
                str(vendor.get("supplierCity") or ""),
                str(vendor.get("supplierState") or ""),
            ]
        ).lower()
    return any(t in loc for t in tokens)


def extract_city_from_text(text: str) -> str | None:
    """Best-effort city extraction from user prose when UI city field is empty."""
    patterns = [
        r"\bin\s+([A-Za-z][A-Za-z\s]{1,30}?)\s*$",
        r"\bin\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\s*[,.]|\s+for|\s+near|\s+please|\s+only)",
        r"\b(?:city|location)\s*[:=]\s*([A-Za-z][A-Za-z\s]{1,30})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            city = m.group(1).strip(" .,")
            # drop trailing fluff words
            city = re.sub(
                r"\b(suppliers?|vendors?|companies|sellers?|please|now)\b",
                "",
                city,
                flags=re.I,
            ).strip()
            if 2 <= len(city) <= 40:
                return city
    return None


PRESENT_SYSTEM = """You are Godown's results editor for IndiaMART procurement research.

You receive:
1) The user's request (and any city/product constraints)
2) Raw vendor JSON from tools (may include off-city / weakly relevant hits — IndiaMART is noisy)

Your job:
- Keep ONLY vendors that match the user's constraints (especially city if specified).
- Prefer exact city matches; for Delhi also accept New Delhi / Delhi NCR.
- Drop clearly irrelevant product matches (wrong category vs the query).
- If nothing relevant remains, say so clearly and set kept_indexes to [].
- Never invent GST, phone, price, address, ratings, or URLs.
- Write a clear, structured answer for the user in markdown.
- Be honest if few/no vendors match the city: say so and do not pad with wrong-city suppliers.

Return STRICT JSON only (no markdown fences):
{
  "message": "markdown answer for the user",
  "kept_indexes": [0, 2],
  "dropped_reason": "short note if anything dropped, else null"
}

kept_indexes are 0-based indexes into the vendors array you were given.
"""


def present_vendors_for_user(
    llm: OpenAI,
    settings: Settings,
    *,
    user_request: str,
    city: str | None,
    vendors: list[Vendor],
    max_results: int,
) -> tuple[str, list[Vendor], str | None]:
    """LLM presentation layer: filter + rewrite user-facing answer."""
    if not vendors:
        return (
            "No matching suppliers were returned from IndiaMART for that request. "
            "Try a broader product keyword or a nearby city.",
            [],
            None,
        )

    # Deterministic pre-filter by city before LLM (hard gate)
    pre = vendors
    dropped_city = 0
    if city:
        matched = [v for v in vendors if vendor_matches_city(v, city)]
        dropped_city = len(vendors) - len(matched)
        pre = matched if matched else []

    if city and not pre:
        return (
            f"IndiaMART returned listings, but none were in **{city}** "
            f"({dropped_city} off-city results filtered out). "
            "Try a nearby city (e.g. Noida / Gurugram for NCR) or broaden the product query.",
            [],
            "all_filtered_by_city",
        )

    compact = []
    for i, v in enumerate(pre[: max(max_results * 2, 20)]):
        compact.append(
            {
                "index": i,
                "companyName": v.companyName,
                "productName": v.productName,
                "supplierCity": v.supplierCity,
                "supplierState": v.supplierState,
                "price": v.price,
                "phone": v.phone,
                "gstNumber": v.gstNumber,
                "supplierRating": v.supplierRating,
                "ratingCount": v.ratingCount,
                "supplierUrl": v.supplierUrl,
                "productUrl": v.productUrl,
                "yearsOnPlatform": v.yearsOnPlatform,
                "hasProfile": bool(v.profile),
                "reviewCount": len(v.reviews or []),
            }
        )

    payload = {
        "user_request": user_request,
        "required_city": city,
        "vendors": compact,
    }

    resp = llm.chat.completions.create(
        model=settings.resolved_model(),
        messages=[
            {"role": "system", "content": PRESENT_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, default=str),
            },
        ],
        temperature=0.2,
    )
    raw = (resp.choices[0].message.content or "").strip()
    # strip optional fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # fallback: show pre-filtered list with a simple summary
        lines = [
            f"Found **{len(pre[:max_results])}** suppliers"
            + (f" in **{city}**" if city else "")
            + ":",
            "",
        ]
        for v in pre[:max_results]:
            lines.append(
                f"- **{v.companyName or 'Unknown'}** — {v.productName or '—'} "
                f"({v.supplierCity or '?'}"
                f"{', ' + v.supplierState if v.supplierState else ''})"
                + (f" · {v.price}" if v.price else "")
                + (f" · GST {v.gstNumber}" if v.gstNumber else "")
            )
        if dropped_city:
            lines.append("")
            lines.append(f"_Filtered out {dropped_city} off-city IndiaMART hits._")
        return "\n".join(lines), pre[:max_results], "present_json_parse_fallback"

    kept = data.get("kept_indexes")
    if kept is None:
        kept = list(range(min(len(pre), max_results)))
    if not isinstance(kept, list):
        kept = []
    kept_vendors: list[Vendor] = []
    for idx in kept:
        if isinstance(idx, int) and 0 <= idx < len(pre):
            v = pre[idx]
            if city and not vendor_matches_city(v, city):
                continue
            kept_vendors.append(v)
        if len(kept_vendors) >= max_results:
            break

    # Do NOT fall back to all vendors when the editor intentionally kept none
    message = data.get("message") or "Here are the matching suppliers."
    reason = data.get("dropped_reason")
    if dropped_city and isinstance(reason, str):
        reason = f"{reason}; hard-filtered {dropped_city} off-city"
    elif dropped_city:
        reason = f"hard-filtered {dropped_city} off-city"

    return str(message), kept_vendors, reason if isinstance(reason, str) else None
