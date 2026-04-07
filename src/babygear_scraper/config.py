"""Scraper configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .models import Category, Platform

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "babygear.db"

# Major baby gear brands for classification
KNOWN_BRANDS = [
    "UPPAbaby", "Bugaboo", "Nuna", "Chicco", "Graco", "Britax", "Doona",
    "Baby Jogger", "BOB", "Thule", "Stokke", "Cybex", "Maxi-Cosi",
    "Ergobaby", "BabyBjorn", "Lillebaby", "Tula", "Clek", "Diono",
    "4moms", "Halo", "Owlet", "Nanit", "Infant Optics", "Eufy",
    "Spectra", "Medela", "Elvie", "Willow", "Motif",
    "Pottery Barn Kids", "DaVinci", "Babyletto", "Delta Children",
    "OXO Tot", "Stokke Tripp Trapp", "BABYBJÖRN",
]

# Category keyword mapping for classification
CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.STROLLER: [
        "stroller", "pram", "pushchair", "jogger", "bassinet stroller",
        "travel system", "double stroller", "umbrella stroller",
    ],
    Category.CAR_SEAT: [
        "car seat", "carseat", "infant seat", "booster seat",
        "convertible seat", "travel system",
    ],
    Category.CRIB: [
        "crib", "bassinet", "pack n play", "pack and play", "playard",
        "mini crib", "portable crib", "cosleeper", "co-sleeper",
    ],
    Category.HIGH_CHAIR: [
        "high chair", "highchair", "booster seat dining",
        "feeding chair", "tripp trapp",
    ],
    Category.MONITOR: [
        "baby monitor", "video monitor", "audio monitor", "owlet",
        "nanit", "infant optics",
    ],
    Category.BREAST_PUMP: [
        "breast pump", "breastpump", "pump parts", "spectra", "medela pump",
        "elvie pump", "willow pump", "pumping",
    ],
    Category.CARRIER: [
        "baby carrier", "wrap carrier", "ring sling", "structured carrier",
        "ergo carrier", "ergobaby", "babybjorn carrier", "lillebaby",
    ],
}


class MetroArea(BaseModel):
    """A target metro area for scraping."""

    name: str = Field(description="Human-readable metro area name")
    fb_location_id: Optional[str] = Field(None, description="Facebook location/city ID")
    craigslist_subdomain: Optional[str] = Field(None, description="e.g. 'sfbay' for sfbay.craigslist.org")
    offerup_location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_miles: int = 30


class ScraperConfig(BaseModel):
    """Top-level scraper configuration."""

    db_path: Path = DEFAULT_DB_PATH
    metro_areas: list[MetroArea] = Field(default_factory=lambda: [
        MetroArea(
            name="boston_ma",
            fb_location_id="boston",
            craigslist_subdomain="boston",
            offerup_location="boston-ma",
            latitude=42.3601,
            longitude=-71.0589,
        ),
    ])
    categories: list[Category] = Field(
        default_factory=lambda: list(Category)[:-1]  # All except OTHER
    )
    platforms: list[Platform] = Field(
        default_factory=lambda: [Platform.FACEBOOK_MARKETPLACE]
    )
    request_delay_seconds: float = Field(2.0, description="Min delay between requests")
    max_delay_seconds: float = Field(5.0, description="Max delay (randomized)")
    max_pages_per_category: int = Field(10, description="Max pagination depth")
    max_retries: int = 3
    headless: bool = True
    user_data_dir: Optional[Path] = None
    schedule_hour: int = Field(6, description="Hour of day for daily run (0-23)")
    schedule_minute: int = 0
