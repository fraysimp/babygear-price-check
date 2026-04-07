"""SQLite database layer for storing scraped listings."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Category, Condition, Listing, Platform, ScrapeRun

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    brand TEXT,
    model TEXT,
    category TEXT NOT NULL DEFAULT 'other',
    condition TEXT NOT NULL DEFAULT 'unknown',
    price_cents INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    location TEXT,
    metro_area TEXT NOT NULL,
    listing_date TEXT,
    photo_urls TEXT NOT NULL DEFAULT '[]',
    seller_name TEXT,
    scraped_at TEXT NOT NULL,
    raw_data TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform, platform_id)
);

CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);
CREATE INDEX IF NOT EXISTS idx_listings_brand ON listings(brand);
CREATE INDEX IF NOT EXISTS idx_listings_metro ON listings(metro_area);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_cents);
CREATE INDEX IF NOT EXISTS idx_listings_scraped ON listings(scraped_at);
CREATE INDEX IF NOT EXISTS idx_listings_platform_id ON listings(platform, platform_id);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    metro_area TEXT NOT NULL,
    category TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    listings_found INTEGER NOT NULL DEFAULT 0,
    listings_new INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_started ON scrape_runs(started_at);
"""


class Database:
    """SQLite database for baby gear listings."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def upsert_listing(self, listing: Listing) -> bool:
        """Insert or update a listing. Returns True if it was a new insert."""
        assert self.conn is not None
        data = {
            "platform": listing.platform.value,
            "platform_id": listing.platform_id,
            "url": listing.url,
            "title": listing.title,
            "description": listing.description,
            "brand": listing.brand,
            "model": listing.model,
            "category": listing.category.value,
            "condition": listing.condition.value,
            "price_cents": listing.price_cents,
            "currency": listing.currency,
            "location": listing.location,
            "metro_area": listing.metro_area,
            "listing_date": listing.listing_date.isoformat() if listing.listing_date else None,
            "photo_urls": json.dumps(listing.photo_urls),
            "seller_name": listing.seller_name,
            "scraped_at": listing.scraped_at.isoformat(),
            "raw_data": json.dumps(listing.raw_data) if listing.raw_data else None,
        }

        cursor = self.conn.execute(
            "SELECT id FROM listings WHERE platform = ? AND platform_id = ?",
            (data["platform"], data["platform_id"]),
        )
        existing = cursor.fetchone()

        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in data if k not in ("platform", "platform_id"))
            values = [v for k, v in data.items() if k not in ("platform", "platform_id")]
            values.extend([data["platform"], data["platform_id"]])
            self.conn.execute(
                f"UPDATE listings SET {set_clause}, updated_at = datetime('now') "
                f"WHERE platform = ? AND platform_id = ?",
                values,
            )
            self.conn.commit()
            return False
        else:
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            self.conn.execute(
                f"INSERT INTO listings ({cols}) VALUES ({placeholders})",
                list(data.values()),
            )
            self.conn.commit()
            return True

    def start_scrape_run(self, run: ScrapeRun) -> int:
        """Record the start of a scrape run. Returns the run ID."""
        assert self.conn is not None
        cursor = self.conn.execute(
            "INSERT INTO scrape_runs (platform, metro_area, category, started_at) "
            "VALUES (?, ?, ?, ?)",
            (run.platform.value, run.metro_area, run.category.value, run.started_at.isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def finish_scrape_run(
        self, run_id: int, listings_found: int, listings_new: int, error: Optional[str] = None
    ) -> None:
        assert self.conn is not None
        self.conn.execute(
            "UPDATE scrape_runs SET finished_at = ?, listings_found = ?, listings_new = ?, error = ? "
            "WHERE id = ?",
            (datetime.utcnow().isoformat(), listings_found, listings_new, error, run_id),
        )
        self.conn.commit()

    def get_listing_count(self, category: Optional[str] = None, metro_area: Optional[str] = None) -> int:
        assert self.conn is not None
        query = "SELECT COUNT(*) FROM listings WHERE 1=1"
        params: list = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if metro_area:
            query += " AND metro_area = ?"
            params.append(metro_area)
        return self.conn.execute(query, params).fetchone()[0]

    def get_price_stats(self, category: str, metro_area: Optional[str] = None) -> dict:
        """Get price statistics for a category."""
        assert self.conn is not None
        query = """
            SELECT
                COUNT(*) as count,
                MIN(price_cents) as min_price,
                MAX(price_cents) as max_price,
                AVG(price_cents) as avg_price,
                category
            FROM listings
            WHERE category = ? AND price_cents IS NOT NULL
        """
        params: list = [category]
        if metro_area:
            query += " AND metro_area = ?"
            params.append(metro_area)
        row = self.conn.execute(query, params).fetchone()
        return {
            "count": row[0],
            "min_price_cents": row[1],
            "max_price_cents": row[2],
            "avg_price_cents": round(row[3]) if row[3] else None,
        }
