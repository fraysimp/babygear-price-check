"""CLI entry point for the baby gear scraper."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import ScraperConfig
from .database import Database
from .models import Category

console = Console()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config(config_path: Path | None) -> ScraperConfig:
    if config_path and config_path.exists():
        data = json.loads(config_path.read_text())
        return ScraperConfig(**data)
    return ScraperConfig()


@click.group()
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None, help="Config JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--db", type=click.Path(path_type=Path), default=None, help="Database path override")
@click.pass_context
def main(ctx, config, verbose, db):
    """Baby Gear Price Scraper - Collect pricing data from online marketplaces."""
    setup_logging(verbose)
    cfg = load_config(config)
    if db:
        cfg.db_path = db
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg


@main.command()
@click.pass_context
def scrape(ctx):
    """Run a one-time scrape across all configured platforms and metro areas."""
    from .orchestrator import run_scrape

    cfg = ctx.obj["config"]
    console.print("[bold]Starting scrape...[/bold]")

    summary = asyncio.run(run_scrape(cfg))

    console.print(f"\n[bold green]Scrape complete![/bold green]")
    console.print(f"  Listings found: {summary['total_found']}")
    console.print(f"  New listings:   {summary['total_new']}")
    if summary["errors"]:
        console.print(f"  [red]Errors: {len(summary['errors'])}[/red]")
        for err in summary["errors"]:
            console.print(f"    - {err}")


@main.command()
@click.pass_context
def schedule(ctx):
    """Start the scheduler for daily automated scraping."""
    from .scheduler import run_scheduler_forever

    cfg = ctx.obj["config"]
    console.print(
        f"[bold]Starting scheduler (daily at {cfg.schedule_hour:02d}:{cfg.schedule_minute:02d})...[/bold]"
    )
    console.print("Press Ctrl+C to stop.")
    asyncio.run(run_scheduler_forever(cfg))


@main.command()
@click.option("--category", "-cat", type=click.Choice([c.value for c in Category]), default=None)
@click.option("--metro", "-m", type=str, default=None)
@click.pass_context
def stats(ctx, category, metro):
    """Show database statistics and price summaries."""
    cfg = ctx.obj["config"]
    db = Database(cfg.db_path)

    with db:
        total = db.get_listing_count()
        console.print(f"\n[bold]Database: {cfg.db_path}[/bold]")
        console.print(f"Total listings: {total}\n")

        table = Table(title="Listings by Category")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Avg Price", justify="right", style="green")
        table.add_column("Min Price", justify="right")
        table.add_column("Max Price", justify="right")

        categories = [category] if category else [c.value for c in Category]
        for cat in categories:
            count = db.get_listing_count(category=cat, metro_area=metro)
            if count > 0:
                price_stats = db.get_price_stats(cat, metro_area=metro)
                avg = f"${price_stats['avg_price_cents'] / 100:.0f}" if price_stats["avg_price_cents"] else "N/A"
                min_p = f"${price_stats['min_price_cents'] / 100:.0f}" if price_stats["min_price_cents"] is not None else "N/A"
                max_p = f"${price_stats['max_price_cents'] / 100:.0f}" if price_stats["max_price_cents"] is not None else "N/A"
                table.add_row(cat, str(count), avg, min_p, max_p)
            else:
                table.add_row(cat, "0", "N/A", "N/A", "N/A")

        console.print(table)


@main.command()
@click.pass_context
def init_db(ctx):
    """Initialize the database (creates tables if they don't exist)."""
    cfg = ctx.obj["config"]
    db = Database(cfg.db_path)
    with db:
        console.print(f"[green]Database initialized at {cfg.db_path}[/green]")


if __name__ == "__main__":
    main()
