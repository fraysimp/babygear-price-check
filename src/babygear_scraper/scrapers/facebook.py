"""Facebook Marketplace scraper using Playwright for browser automation.

Facebook Marketplace renders client-side with React/GraphQL, so we use a real
browser via Playwright to load pages and extract listing data from the DOM.

ToS note: This scraper accesses only publicly visible data (no login required).
The long-term strategy is to move toward direct seller onboarding via an API.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import AsyncIterator, Optional
from urllib.parse import quote_plus

from ..classifier import classify_category, extract_brand, parse_condition, parse_price
from ..config import CATEGORY_KEYWORDS, ScraperConfig
from ..models import Category, Condition, Listing, Platform
from ..scraper_base import BaseScraper

logger = logging.getLogger(__name__)

# Search terms per category for Facebook Marketplace
FB_SEARCH_TERMS: dict[Category, list[str]] = {
    Category.STROLLER: ["baby stroller", "jogging stroller", "double stroller"],
    Category.CAR_SEAT: ["infant car seat", "convertible car seat", "baby car seat"],
    Category.CRIB: ["baby crib", "bassinet", "pack n play"],
    Category.HIGH_CHAIR: ["high chair baby", "baby highchair"],
    Category.MONITOR: ["baby monitor", "video baby monitor"],
    Category.BREAST_PUMP: ["breast pump", "spectra pump", "medela pump"],
    Category.CARRIER: ["baby carrier", "baby wrap", "ergo carrier"],
}


class FacebookMarketplaceScraper(BaseScraper):
    """Scraper for Facebook Marketplace using Playwright."""

    platform = Platform.FACEBOOK_MARKETPLACE

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self._browser = None
        self._context = None

    async def setup(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        # Block unnecessary resources to speed up scraping
        await self._context.route(
            re.compile(r"\.(png|jpg|jpeg|gif|svg|woff|woff2|mp4|webm)$"),
            lambda route: route.abort(),
        )

    async def teardown(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _build_search_url(self, query: str, location_id: str) -> str:
        encoded = quote_plus(query)
        return f"https://www.facebook.com/marketplace/{location_id}/search?query={encoded}&exact=false"

    async def _extract_listings_from_page(
        self, page, category: Category, metro_area: str
    ) -> list[Listing]:
        """Extract listing data from the current page DOM."""
        listings: list[Listing] = []

        # FB Marketplace uses various selectors; these target the listing cards
        # The exact selectors may need updating as FB changes their DOM
        cards = await page.query_selector_all(
            'div[class*="x9f619"] a[href*="/marketplace/item/"]'
        )

        if not cards:
            # Fallback: try broader selector
            cards = await page.query_selector_all('a[href*="/marketplace/item/"]')

        logger.info("Found %d listing cards on page", len(cards))

        for card in cards:
            try:
                listing = await self._parse_card(card, category, metro_area)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug("Failed to parse card: %s", e)
                continue

        return listings

    async def _parse_card(self, card, category: Category, metro_area: str) -> Optional[Listing]:
        """Parse a single listing card element into a Listing model."""
        href = await card.get_attribute("href") or ""

        # Extract platform_id from URL like /marketplace/item/123456789/
        id_match = re.search(r"/marketplace/item/(\d+)", href)
        if not id_match:
            return None
        platform_id = id_match.group(1)

        # Get text content from the card
        text_content = await card.inner_text()
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]

        if len(lines) < 2:
            return None

        # Typically: price on first line, title on second, location on third
        price_text = lines[0] if lines else ""
        title = lines[1] if len(lines) > 1 else lines[0]
        location = lines[2] if len(lines) > 2 else None

        price_cents = parse_price(price_text)
        # "Free" listings
        if "free" in price_text.lower():
            price_cents = 0

        brand = extract_brand(title)
        condition = parse_condition(title)

        # Refine category if the broad category doesn't match well
        refined_category = classify_category(title)
        if refined_category != Category.OTHER:
            category = refined_category

        url = f"https://www.facebook.com/marketplace/item/{platform_id}/"

        return Listing(
            platform=Platform.FACEBOOK_MARKETPLACE,
            platform_id=platform_id,
            url=url,
            title=title,
            description=None,  # Would need to visit detail page
            brand=brand,
            model=None,
            category=category,
            condition=condition,
            price_cents=price_cents,
            location=location,
            metro_area=metro_area,
            photo_urls=[],
            scraped_at=datetime.utcnow(),
        )

    async def _scroll_for_more(self, page) -> bool:
        """Scroll down to trigger lazy loading of more results. Returns True if new content loaded."""
        prev_count = len(await page.query_selector_all('a[href*="/marketplace/item/"]'))
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        new_count = len(await page.query_selector_all('a[href*="/marketplace/item/"]'))
        return new_count > prev_count

    async def scrape_category(
        self, category: Category, metro_area_name: str
    ) -> AsyncIterator[Listing]:
        """Scrape all listings for a category in a metro area."""
        assert self._context is not None

        search_terms = FB_SEARCH_TERMS.get(category, [category.value.replace("_", " ")])

        # Find the metro area config to get the FB location ID
        location_id = "marketplace"  # default
        for metro in self.config.metro_areas:
            if metro.name == metro_area_name and metro.fb_location_id:
                location_id = metro.fb_location_id
                break

        seen_ids: set[str] = set()

        for term in search_terms:
            url = self._build_search_url(term, location_id)
            page = await self._context.new_page()

            try:
                logger.info("Searching FB Marketplace: %s", term)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)  # Let React render

                # Handle cookie/login prompts by closing modals
                try:
                    close_btn = await page.query_selector('[aria-label="Close"]')
                    if close_btn:
                        await close_btn.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                pages_scraped = 0
                while pages_scraped < self.config.max_pages_per_category:
                    listings = await self._extract_listings_from_page(page, category, metro_area_name)

                    for listing in listings:
                        if listing.platform_id not in seen_ids:
                            seen_ids.add(listing.platform_id)
                            yield listing

                    pages_scraped += 1

                    # Try to load more via scrolling
                    has_more = await self._scroll_for_more(page)
                    if not has_more:
                        break

                    await self.delay()

            except Exception as e:
                logger.error("Error scraping term '%s': %s", term, e)
            finally:
                await page.close()

            await self.delay()
