"""Base scraper interface and shared utilities."""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator

from .config import ScraperConfig
from .models import Category, Listing, Platform, ScrapeRun

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for marketplace scrapers."""

    platform: Platform

    def __init__(self, config: ScraperConfig):
        self.config = config

    async def delay(self) -> None:
        """Random delay between requests for rate limiting."""
        wait = random.uniform(self.config.request_delay_seconds, self.config.max_delay_seconds)
        logger.debug("Rate limit delay: %.1fs", wait)
        await asyncio.sleep(wait)

    @abstractmethod
    async def setup(self) -> None:
        """Initialize browser/session. Called once before scraping starts."""

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up browser/session."""

    @abstractmethod
    async def scrape_category(
        self, category: Category, metro_area_name: str
    ) -> AsyncIterator[Listing]:
        """Scrape listings for a single category in a metro area.

        Yields Listing objects as they are found. Handles pagination internally.
        """
        yield  # type: ignore[misc]  # make this a generator for type checking

    async def run_full_scrape(self, metro_area_name: str) -> list[ScrapeRun]:
        """Run a full scrape across all configured categories for a metro area."""
        runs: list[ScrapeRun] = []
        await self.setup()
        try:
            for category in self.config.categories:
                run = ScrapeRun(
                    platform=self.platform,
                    metro_area=metro_area_name,
                    category=category,
                    started_at=datetime.utcnow(),
                )
                logger.info(
                    "Scraping %s / %s / %s", self.platform.value, metro_area_name, category.value
                )
                found = 0
                try:
                    async for _listing in self.scrape_category(category, metro_area_name):
                        found += 1
                    run.listings_found = found
                except Exception as e:
                    logger.error("Error scraping %s/%s: %s", metro_area_name, category.value, e)
                    run.error = str(e)
                finally:
                    run.finished_at = datetime.utcnow()
                    runs.append(run)
                await self.delay()
        finally:
            await self.teardown()
        return runs
