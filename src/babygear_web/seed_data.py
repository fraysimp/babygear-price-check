"""Seed the database with realistic Boston-area baby gear listings for demo purposes."""

import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "babygear.db"

METRO = "boston_ma"
PLATFORM = "facebook_marketplace"

BOSTON_LOCATIONS = [
    "Cambridge, MA", "Somerville, MA", "Brookline, MA", "Newton, MA",
    "Arlington, MA", "Medford, MA", "Watertown, MA", "Belmont, MA",
    "Lexington, MA", "Waltham, MA", "Needham, MA", "Wellesley, MA",
    "Jamaica Plain, MA", "South Boston, MA", "Dorchester, MA",
    "Back Bay, Boston", "Charlestown, MA", "Allston, MA",
    "Quincy, MA", "Milton, MA",
]

# category -> [(brand, model, base_price_cents)]
CATALOG = {
    "stroller": [
        ("UPPAbaby", "Vista V2", 45000),
        ("UPPAbaby", "Cruz V2", 32000),
        ("UPPAbaby", "Minu V2", 25000),
        ("Bugaboo", "Fox 5", 50000),
        ("Bugaboo", "Butterfly", 28000),
        ("Nuna", "MIXX Next", 42000),
        ("Nuna", "TRVL", 30000),
        ("Baby Jogger", "City Mini GT2", 22000),
        ("Baby Jogger", "City Select 2", 35000),
        ("Chicco", "Bravo Trio", 18000),
        ("BOB", "Wayfinder", 35000),
        ("BOB", "Alterrain Pro", 45000),
        ("Thule", "Urban Glide 2", 38000),
        ("Mockingbird", "Single-to-Double", 25000),
        ("Doona", "Car Seat & Stroller", 40000),
    ],
    "car_seat": [
        ("Nuna", "RAVA", 35000),
        ("Nuna", "PIPA Lite RX", 30000),
        ("Chicco", "KeyFit 35", 18000),
        ("Chicco", "NextFit Max", 25000),
        ("Graco", "4Ever DLX", 22000),
        ("Graco", "SnugRide 35", 14000),
        ("UPPAbaby", "Mesa Max", 32000),
        ("Britax", "Boulevard ClickTight", 28000),
        ("Britax", "One4Life", 25000),
        ("Clek", "Foonf", 40000),
        ("Clek", "Liing", 30000),
        ("Maxi-Cosi", "Mico Luxe", 22000),
    ],
    "crib": [
        ("Babyletto", "Hudson", 30000),
        ("Babyletto", "Lolly", 28000),
        ("Babyletto", "Gelato", 32000),
        ("Pottery Barn Kids", "Kendall", 45000),
        ("IKEA", "Sniglar", 8000),
        ("IKEA", "Sundvik", 15000),
        ("Delta Children", "Canton", 18000),
        ("DaVinci", "Kalani", 22000),
        ("Storkcraft", "Tuscany", 25000),
        ("Nestig", "Cloud Crib", 35000),
    ],
    "high_chair": [
        ("Stokke", "Tripp Trapp", 30000),
        ("Nuna", "ZAAZ", 20000),
        ("OXO Tot", "Sprout", 18000),
        ("IKEA", "Antilop", 2500),
        ("Abiie", "Beyond", 17000),
        ("Peg Perego", "Siesta", 25000),
        ("Graco", "Table2Table", 12000),
        ("BabyBjorn", "High Chair", 22000),
    ],
    "monitor": [
        ("Nanit", "Pro", 22000),
        ("Nanit", "Pro Complete", 30000),
        ("Owlet", "Dream Sock", 28000),
        ("Owlet", "Cam 2", 15000),
        ("eufy", "SpaceView Pro", 14000),
        ("Infant Optics", "DXR-8 Pro", 16000),
        ("VTech", "RM5764HD", 10000),
        ("Motorola", "Halo+ MBP944", 12000),
    ],
    "breast_pump": [
        ("Spectra", "S1 Plus", 15000),
        ("Spectra", "S2 Plus", 10000),
        ("Medela", "Pump In Style", 18000),
        ("Medela", "Freestyle Flex", 25000),
        ("Elvie", "Double Electric", 35000),
        ("Willow", "Go", 22000),
        ("Motif", "Luna", 8000),
        ("BabyBuddha", "Portable", 10000),
    ],
    "carrier": [
        ("Ergobaby", "Omni 360", 14000),
        ("Ergobaby", "Embrace", 6000),
        ("BabyBjorn", "Mini", 6000),
        ("BabyBjorn", "Harmony", 18000),
        ("Artipoppe", "Zeitgeist", 35000),
        ("LILLEbaby", "Complete All Seasons", 10000),
        ("Solly Baby", "Wrap", 5000),
        ("Tula", "Explore", 14000),
    ],
    "swing": [
        ("4moms", "mamaRoo 5", 18000),
        ("4moms", "rockaRoo", 12000),
        ("Graco", "Soothe My Way", 12000),
        ("Fisher-Price", "Snuga Swing", 8000),
        ("Ingenuity", "ConvertMe", 7000),
    ],
    "bouncer": [
        ("BabyBjorn", "Bouncer Bliss", 16000),
        ("BabyBjorn", "Bouncer Balance", 20000),
        ("4moms", "bounceRoo", 10000),
        ("Fisher-Price", "Kick n Play", 5000),
    ],
    "bassinet": [
        ("SNOO", "Smart Sleeper", 120000),
        ("Halo", "BassiNest Swivel", 18000),
        ("UPPAbaby", "Bassinet Stand", 10000),
        ("Chicco", "Close To You", 15000),
        ("Baby Delight", "Beside Me Dreamer", 10000),
    ],
    "playpen": [
        ("4moms", "Breeze Plus", 18000),
        ("Graco", "Pack 'n Play", 10000),
        ("Lotus", "Travel Crib", 22000),
        ("BabyBjorn", "Travel Crib Light", 25000),
        ("Guava", "Lotus", 22000),
    ],
    "diaper_bag": [
        ("Petunia Pickle Bottom", "Boxy Backpack", 15000),
        ("Dagne Dover", "Indi Diaper Backpack", 18000),
        ("Freshly Picked", "Classic Diaper Bag", 16000),
        ("JuJuBe", "BFF", 12000),
        ("Skip Hop", "Forma Backpack", 6000),
    ],
}

CONDITIONS = ["new", "like_new", "good", "fair", "poor"]
CONDITION_WEIGHTS = [0.05, 0.20, 0.45, 0.25, 0.05]
CONDITION_PRICE_FACTOR = {
    "new": (0.85, 1.0),
    "like_new": (0.65, 0.85),
    "good": (0.45, 0.70),
    "fair": (0.30, 0.50),
    "poor": (0.15, 0.35),
}

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
"""


def generate_title(brand: str, model: str, condition: str, category: str) -> str:
    cond_labels = {
        "new": "Brand New",
        "like_new": "Like New",
        "good": "Great Condition",
        "fair": "Good Condition",
        "poor": "Used",
    }
    prefixes = [
        f"{brand} {model} - {cond_labels.get(condition, '')}",
        f"{brand} {model} {category.replace('_', ' ')}",
        f"{cond_labels.get(condition, '')} {brand} {model}",
        f"{brand} {model}",
    ]
    return random.choice(prefixes)


def seed():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)

    now = datetime.utcnow()
    listings = []

    for category, items in CATALOG.items():
        for brand, model, base_price in items:
            # Generate 5-15 listings per item
            n = random.randint(5, 15)
            for _ in range(n):
                condition = random.choices(CONDITIONS, CONDITION_WEIGHTS)[0]
                low_f, high_f = CONDITION_PRICE_FACTOR[condition]
                factor = random.uniform(low_f, high_f)
                # Add some market noise
                noise = random.uniform(0.85, 1.15)
                price = round(base_price * factor * noise)

                days_ago = random.randint(0, 60)
                listing_date = now - timedelta(days=days_ago)
                scraped_at = listing_date + timedelta(hours=random.randint(1, 12))

                pid = uuid.uuid4().hex[:16]
                location = random.choice(BOSTON_LOCATIONS)
                title = generate_title(brand, model, condition, category)

                listings.append((
                    PLATFORM, pid,
                    f"https://facebook.com/marketplace/item/{pid}",
                    title, None, brand, model, category, condition,
                    price, "USD", location, METRO,
                    listing_date.isoformat(),
                    "[]", None, scraped_at.isoformat(), None,
                ))

    conn.executemany(
        """INSERT OR IGNORE INTO listings
        (platform, platform_id, url, title, description, brand, model,
         category, condition, price_cents, currency, location, metro_area,
         listing_date, photo_urls, seller_name, scraped_at, raw_data)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        listings,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()
    print(f"Seeded {len(listings)} listings ({count} total in DB) for {METRO}")


if __name__ == "__main__":
    seed()
