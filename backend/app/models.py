from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Mode(str, Enum):
    fast = "fast"
    hybrid = "hybrid"
    full = "full"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    mode: Mode = Mode.hybrid
    maxResults: int = Field(default=20, ge=1, le=200)
    city: str | None = None


class ToolTrace(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_preview: str
    ok: bool = True


class EgressInfo(BaseModel):
    country_code: str | None = None
    country: str | None = None
    ip: str | None = None
    org: str | None = None
    ok: bool = False
    error: str | None = None


class VendorReview(BaseModel):
    reviewerName: str | None = None
    location: str | None = None
    date: str | None = None
    stars: float | None = None
    reviewText: str | None = None
    productName: str | None = None


class Vendor(BaseModel):
    mode: str = "search"
    productName: str | None = None
    companyName: str | None = None
    supplierCity: str | None = None
    supplierState: str | None = None
    price: str | None = None
    currency: str | None = None
    moq: str | None = None
    phone: str | None = None
    gstNumber: str | None = None
    supplierId: str | None = None
    glusrid_b64: str | None = None
    productUrl: str | None = None
    supplierUrl: str | None = None
    imageUrl: str | None = None
    supplierRating: float | None = None
    ratingCount: int | None = None
    iecflag: Any = None
    isverifiedexporter: Any = None
    gstVerified: bool | None = None
    trustseal: bool | None = None
    yearsOnPlatform: str | None = None
    scrapedAt: str | None = None
    profile: dict[str, Any] | None = None
    pdp: dict[str, Any] | None = None
    reviews: list[VendorReview] | None = None


class ChatResponse(BaseModel):
    message: str
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    vendors: list[Vendor] = Field(default_factory=list)
    egress: EgressInfo | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    egress: EgressInfo
    search_probe: dict[str, Any] = Field(default_factory=dict)
    llm_configured: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    # Alias kept for older UI builds
    glm_configured: bool = False
