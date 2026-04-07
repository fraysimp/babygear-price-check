"""Schedule daily scrape runs using APScheduler."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import ScraperConfig
from .orchestrator import run_scrape

logger = logging.getLogger(__name__)


async def _run_job(config: ScraperConfig) -> None:
    """Wrapper to run the scrape as a scheduled job."""
    logger.info("Scheduled scrape starting...")
    try:
        summary = await run_scrape(config)
        logger.info("Scheduled scrape finished: %s", summary)
    except Exception:
        logger.exception("Scheduled scrape failed")


def start_scheduler(config: ScraperConfig) -> AsyncIOScheduler:
    """Start the APScheduler with a daily cron trigger.

    Returns the scheduler instance (already started).
    """
    scheduler = AsyncIOScheduler()

    trigger = CronTrigger(
        hour=config.schedule_hour,
        minute=config.schedule_minute,
    )

    scheduler.add_job(
        _run_job,
        trigger=trigger,
        args=[config],
        id="daily_scrape",
        name="Daily baby gear scrape",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started. Next run at %s",
        scheduler.get_job("daily_scrape").next_run_time,
    )
    return scheduler


async def run_scheduler_forever(config: ScraperConfig) -> None:
    """Start the scheduler and block until interrupted."""
    scheduler = start_scheduler(config)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
