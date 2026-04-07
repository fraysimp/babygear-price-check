"""Data models for baby gear listings."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Condition(str, Enum):
    NEW = "new"
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


class Category(str, Enum):
    STROLLER = "stroller"
    CAR_SEAT = "car_seat"
    CRIB = "crib"
    HIGH_CHAIR = "high_chair"
    MONITOR = "monitor"
    BREAST_PUMP = "breast_pump"
    CARRIER = "carrier"
    OTHER = "other"


class Platform(str, Enum):
    FACEBOOK_MARKETPLACE = "facebook_marketplace"
    CRAIGSLIST = "craigslist"
    OFFERUP = "offerup"


class Listing(BaseModel):
    """A single baby gear listing scraped from a marketplace."""

    platform: Platform
    platform_id: str = Field(description="Unique ID on the source platform")
    url: str
    title: str
    description: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Category = Category.OTHER
    condition: Condition = Condition.UNKNOWN
    price_cents: Optional[int] = Field(None, description="Asking price in cents")
    currency: str = "USD"
    location: Optional[str] = None
    metro_area: str
    listing_date: Optional[datetime] = None
    photo_urls: list[str] = Field(default_factory=list)
    seller_name: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Optional[dict] = None


class ScrapeRun(BaseModel):
    """Metadata for a single scrape execution."""

    id: Optional[int] = None
    platform: Platform
    metro_area: str
    category: Category
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    listings_found: int = 0
    listings_new: int = 0
    error: Optional[str] = None
