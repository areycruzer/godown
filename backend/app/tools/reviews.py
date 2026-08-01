from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.models import VendorReview


def _parse_review_cards(html: str) -> list[VendorReview]:
    soup = BeautifulSoup(html, "lxml")
    reviews: list[VendorReview] = []
    # Heuristic: blocks that look like testimonials
    candidates = soup.select(
        "[class*='review'], [class*='testimonial'], [class*='rating']"
    )
    seen_text: set[str] = set()
    for el in candidates:
        text = el.get_text(" ", strip=True)
        if len(text) < 20 or text in seen_text:
            continue
        stars = None
        m = re.search(r"(\d(?:\.\d)?)\s*(?:/|out of)?\s*5", text)
        if m:
            stars = float(m.group(1))
        # skip pure UI chrome
        if "Write a Review" in text and len(text) < 40:
            continue
        seen_text.add(text)
        reviews.append(
            VendorReview(
                reviewText=text[:800],
                stars=stars,
            )
        )
        if len(reviews) >= 30:
            break
    return reviews


def fetch_reviews(client: httpx.Client, rating_url: str | None) -> list[dict[str, Any]]:
    if not rating_url:
        return []
    try:
        r = client.get(rating_url)
        if r.status_code != 200:
            return []
        return [rv.model_dump() for rv in _parse_review_cards(r.text)]
    except Exception:
        return []


def discover_rating_url(vendor: dict[str, Any]) -> str | None:
    for key in (
        "desktopCatalogRatingUrl",
        "mobileCatalogRatingUrl",
        "ratingUrl",
    ):
        if vendor.get(key):
            return vendor[key]
    profile = vendor.get("profile") or {}
    for key in ("desktopCatalogRatingUrl", "mobileCatalogRatingUrl", "ratingUrl"):
        if profile.get(key):
            return profile[key]
    # guess from supplier url
    url = vendor.get("supplierUrl")
    if url and url.endswith("/"):
        return url + "testimonial.html"
    if url:
        return url.rstrip("/") + "/testimonial.html"
    return None
