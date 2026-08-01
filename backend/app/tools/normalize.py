from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from typing import Any

from app.models import Vendor


def decode_glusrid(b64: str | None) -> str | None:
    if not b64:
        return None
    try:
        return base64.b64decode(b64).decode("utf-8")
    except Exception:
        return None


def _num(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    m = re.search(r"[\d.]+", s.replace(",", ""))
    return float(m.group()) if m else None


def fields_to_vendor(fields: dict[str, Any]) -> Vendor:
    gid = fields.get("glusrid")
    gst_flag = fields.get("gstVerifiedFlag") or fields.get("gst_verification_src_id")
    rating = fields.get("supplier_rating") or fields.get("rating")
    rating_count = fields.get("rating_count")
    return Vendor(
        mode="search",
        productName=fields.get("original_title")
        or fields.get("bl_product_name")
        or fields.get("title"),
        companyName=fields.get("companyname"),
        supplierCity=fields.get("city"),
        supplierState=fields.get("state"),
        price=str(fields.get("itemprice")) if fields.get("itemprice") is not None else fields.get("price_f") or fields.get("indiaPriceFormat"),
        currency=fields.get("itemcurrency") or "INR",
        moq=str(fields.get("moq")) if fields.get("moq") is not None else None,
        phone=fields.get("pns") or fields.get("phone") or fields.get("mobile"),
        gstNumber=fields.get("gstNumber"),
        supplierId=decode_glusrid(gid) if isinstance(gid, str) else None,
        glusrid_b64=gid if isinstance(gid, str) else None,
        productUrl=fields.get("desktop_title_url")
        or fields.get("mobile_title_url")
        or fields.get("title_url")
        or fields.get("url"),
        supplierUrl=fields.get("catalog_url")
        or fields.get("fcpurl")
        or fields.get("desktop_catalog_url")
        or fields.get("mobile_catalog_url"),
        imageUrl=fields.get("large_image") or fields.get("image") or fields.get("photo"),
        supplierRating=_num(rating),
        ratingCount=int(rating_count) if rating_count not in (None, "") else None,
        iecflag=fields.get("iecflag"),
        isverifiedexporter=fields.get("isverifiedexporter"),
        gstVerified=bool(gst_flag) if gst_flag not in (None, "", 0, "0") else None,
        yearsOnPlatform=fields.get("memberSinceDisplay") or fields.get("memberSince"),
        scrapedAt=datetime.now(timezone.utc).isoformat(),
    )


def vendor_dedupe_key(v: Vendor) -> str:
    return v.supplierId or v.supplierUrl or v.productUrl or f"{v.companyName}:{v.productName}"


def vendor_to_dict(v: Vendor) -> dict[str, Any]:
    return v.model_dump(exclude_none=False)
