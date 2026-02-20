"""Main scraper orchestrator.

Coordinates scraping from all sources, deduplicates results,
and saves to JSON data file.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

from scraper.models import Job
from scraper.sources import greenhouse, lever, workday

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
MANUAL_FILE = DATA_DIR / "manual_jobs.json"


def load_existing_jobs() -> List[Job]:
    """Load existing jobs from the data file."""
    if not JOBS_FILE.exists():
        return []
    try:
        with open(JOBS_FILE, "r") as f:
            data = json.load(f)
        return [Job.from_dict(j) for j in data]
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading existing jobs: {e}")
        return []


def load_manual_jobs() -> List[Job]:
    """Load manually curated job listings."""
    if not MANUAL_FILE.exists():
        return []
    try:
        with open(MANUAL_FILE, "r") as f:
            data = json.load(f)
        return [Job.from_dict(j) for j in data]
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading manual jobs: {e}")
        return []


def deduplicate(jobs: List[Job]) -> List[Job]:
    """Remove duplicate job listings based on company + role + URL."""
    seen = set()
    unique = []
    for job in jobs:
        key = (job.company.lower(), job.role.lower(), job.url.lower())
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def save_jobs(jobs: List[Job]):
    """Save jobs to the data file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(JOBS_FILE, "w") as f:
        json.dump([j.to_dict() for j in jobs], f, indent=2)
    logger.info(f"Saved {len(jobs)} jobs to {JOBS_FILE}")


def scrape_all_sources() -> List[Job]:
    """Run all scrapers and collect results."""
    all_jobs = []

    logger.info("Scraping Greenhouse boards...")
    all_jobs.extend(greenhouse.scrape_all())

    logger.info("Scraping Lever boards...")
    all_jobs.extend(lever.scrape_all())

    logger.info("Scraping Workday career sites...")
    all_jobs.extend(workday.scrape_all())

    return all_jobs


def run():
    """Main entry point: scrape, merge, deduplicate, save."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting finance new grad job scraper...")

    # Load existing + manual jobs
    existing = load_existing_jobs()
    manual = load_manual_jobs()
    logger.info(f"Loaded {len(existing)} existing jobs, {len(manual)} manual entries")

    # Scrape new jobs
    scraped = scrape_all_sources()
    logger.info(f"Scraped {len(scraped)} jobs from all sources")

    # Merge and deduplicate
    all_jobs = deduplicate(manual + scraped + existing)
    logger.info(f"Total unique jobs after dedup: {len(all_jobs)}")

    # Sort by date (newest first)
    all_jobs.sort(key=lambda j: j.date_posted or "0000-00-00", reverse=True)

    # Save
    save_jobs(all_jobs)

    logger.info("Scraping complete!")
    return all_jobs


if __name__ == "__main__":
    run()
