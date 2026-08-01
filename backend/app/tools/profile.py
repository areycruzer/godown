from __future__ import annotations

import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


def _extract_script_json(html: str, marker: str) -> dict | None:
    # __NEXT_DATA__
    if marker == "__NEXT_DATA__":
        m = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
    m = re.search(
        rf"window\.{marker}\s*=\s*(\{{.+?\}})\s*;?\s*</script>",
        html,
        re.DOTALL,
    )
    if not m:
        m = re.search(rf"{marker}\s*=\s*(\{{.+?\}})\s*;", html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _walk_interesting(obj: Any, bag: dict[str, Any], depth: int = 0) -> None:
    if depth > 8:
        return
    interesting = {
        "gst",
        "gstNumber",
        "gstin",
        "cin",
        "tan",
        "iec",
        "banker",
        "address",
        "postalAddress",
        "pin",
        "pincode",
        "ceo",
        "contactPerson",
        "ownerName",
        "legalStatus",
        "yearEstablished",
        "paymentModes",
        "shipmentModes",
        "exportDestinations",
        "description",
        "companyName",
        "companyname",
        "email",
        "mobile",
        "phone",
        "categories",
    }
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k)
            if any(x.lower() in lk.lower() for x in interesting):
                if isinstance(v, (str, int, float, bool)) or v is None:
                    bag.setdefault(lk, v)
                elif isinstance(v, list) and v and isinstance(v[0], str):
                    bag.setdefault(lk, v[:20])
            _walk_interesting(v, bag, depth + 1)
    elif isinstance(obj, list):
        for item in obj[:50]:
            _walk_interesting(item, bag, depth + 1)


def _dom_label_extract(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, Any] = {}
    labels = [
        "GST",
        "GST No",
        "GST Number",
        "CIN",
        "TAN",
        "IEC",
        "Banker",
        "CEO",
        "Director",
        "Year of Establishment",
        "Legal Status",
        "Address",
        "Pincode",
    ]
    text = soup.get_text("\n", strip=True)
    for label in labels:
        m = re.search(
            rf"{re.escape(label)}\s*[:\-]?\s*([^\n]{{3,120}})",
            text,
            re.IGNORECASE,
        )
        if m:
            out[label] = m.group(1).strip()
    title = soup.find("title")
    if title:
        out["pageTitle"] = title.get_text(strip=True)
    return out


def fetch_profile(client: httpx.Client, supplier_url: str) -> dict[str, Any]:
    if not supplier_url:
        return {"error": "missing_supplier_url"}
    try:
        r = client.get(supplier_url)
        if r.status_code == 403:
            return {"error": "forbidden", "status": 403, "url": supplier_url}
        if r.status_code != 200:
            return {"error": f"http_{r.status_code}", "url": supplier_url}
        html = r.text
        bag: dict[str, Any] = {"supplierUrl": supplier_url}
        for marker in ("__NEXT_DATA__", "__INITIAL_STATE__"):
            data = _extract_script_json(html, marker)
            if data:
                _walk_interesting(data, bag)
                bag["parsed_from"] = marker
                break
        else:
            bag.update(_dom_label_extract(html))
            bag["parsed_from"] = "dom"
        # also merge DOM labels as fallback for common KYC fields
        dom = _dom_label_extract(html)
        for k, v in dom.items():
            bag.setdefault(k, v)
        return bag
    except Exception as e:
        return {"error": str(e), "url": supplier_url}


def fetch_pdp(client: httpx.Client, product_url: str) -> dict[str, Any]:
    if not product_url:
        return {}
    try:
        r = client.get(product_url)
        if r.status_code != 200:
            return {"error": f"http_{r.status_code}", "url": product_url}
        html = r.text
        bag: dict[str, Any] = {"productUrl": product_url}
        data = _extract_script_json(html, "__NEXT_DATA__")
        if data:
            _walk_interesting(data, bag)
            bag["parsed_from"] = "__NEXT_DATA__"
        else:
            bag.update(_dom_label_extract(html))
            bag["parsed_from"] = "dom"
        return bag
    except Exception as e:
        return {"error": str(e), "url": product_url}
