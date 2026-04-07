"""Orchestrates scraping runs across platforms, categories, and metro areas."""

from __future__ import annotations

import logging
from datetime import datetime

from .config import ScraperConfig
from .database import Database
from .models import Platform, ScrapeRun
from .scraper_base import BaseScraper
from .scrapers.facebook import FacebookMarketplaceScraper

logger = logging.getLogger(__name__)

SCRAPER_MAP: dict[Platform, type[BaseScraper]] = {
    Platform.FACEBOOK_MARKETPLACE: FacebookMarketplaceScraper,
}


async def run_scrape(config: ScraperConfig) -> dict:
    """Execute a full scrape run across all configured platforms and metro areas.

    Returns a summary dict with counts and any errors.
    """
    db = Database(config.db_path)
    db.connect()

    total_found = 0
    total_new = 0
    errors: list[str] = []

    try:
        for platform in config.platforms:
            scraper_cls = SCRAPER_MAP.get(platform)
            if not scraper_cls:
                logger.warning("No scraper implementation for %s", platform.value)
                continue

            scraper = scraper_cls(config)

            for metro in config.metro_areas:
                logger.info("Starting scrape: %s / %s", platform.value, metro.name)
                await scraper.setup()

                try:
                    for category in config.categories:
                        run = ScrapeRun(
                            platform=platform,
                            metro_area=metro.name,
                            category=category,
                        )
                        run_id = db.start_scrape_run(run)

                        found = 0
                        new = 0
                        error = None

                        try:
                            async for listing in scraper.scrape_category(category, metro.name):
                                found += 1
                                is_new = db.upsert_listing(listing)
                                if is_new:
                                    new += 1

                                if found % 25 == 0:
                                    logger.info(
                                        "  %s: %d found, %d new so far",
                                        category.value, found, new,
                                    )
                        except Exception as e:
                            error = str(e)
                            errors.append(f"{platform.value}/{metro.name}/{category.value}: {error}")
                            logger.error("Scrape error: %s", error)

                        db.finish_scrape_run(run_id, found, new, error)
                        total_found += found
                        total_new += new

                        logger.info(
                            "  %s: %d found, %d new", category.value, found, new
                        )
                finally:
                    await scraper.teardown()
    finally:
        db.close()

    summary = {
        "total_found": total_found,
        "total_new": total_new,
        "errors": errors,
        "completed_at": datetime.utcnow().isoformat(),
    }
    logger.info("Scrape complete: %d found, %d new, %d errors", total_found, total_new, len(errors))
    return summary
