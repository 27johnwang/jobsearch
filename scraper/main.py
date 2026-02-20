"""Main scraper orchestrator.

Coordinates scraping from all sources, deduplicates results,
and saves to JSON data file.

Date handling:
  - Scraped jobs use the real ATS date (updated_at / createdAt / postedOn).
  - If the ATS provides no date, today's date is used (date of discovery).
  - Existing jobs keep their original date_posted (date they were first seen).
  - Manual entries should be set to the date they were verified/added.
  - Everything sorts newest-first so fresh postings bubble to the top.
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

from scraper.models import Job
from scraper.sources import greenhouse, lever, workday

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
MANUAL_FILE = DATA_DIR / "manual_jobs.json"


def _job_key(job: Job) -> Tuple[str, str]:
    """Dedup key: (company_lower, url_lower). Role titles change; URLs don't."""
    return (job.company.lower(), job.url.lower())


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


def merge_jobs(existing: List[Job], incoming: List[Job]) -> List[Job]:
    """Merge incoming jobs into existing, preserving earlier discovery dates.

    - If a job URL already exists, keep the EARLIER date_posted (first-seen wins).
    - If a job is new, use its ATS date or fall back to today.
    """
    today = date.today().isoformat()
    by_key: Dict[Tuple[str, str], Job] = {}

    # Index existing jobs (these have the authoritative dates)
    for job in existing:
        key = _job_key(job)
        if key not in by_key:
            by_key[key] = job

    # Merge incoming
    for job in incoming:
        # Stamp jobs that have no date with today
        if not job.date_posted:
            job.date_posted = today

        key = _job_key(job)
        if key in by_key:
            # Already known — keep earlier date
            prev = by_key[key]
            if job.date_posted < prev.date_posted:
                prev.date_posted = job.date_posted
        else:
            by_key[key] = job

    return list(by_key.values())


def save_jobs(jobs: List[Job]):
    """Save jobs to the data file, sorted newest-first."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    jobs.sort(key=lambda j: j.date_posted or "0000-00-00", reverse=True)
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
    """Main entry point: scrape, merge with date-preservation, save."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting finance new grad job scraper...")

    # Load existing + manual jobs
    existing = load_existing_jobs()
    manual = load_manual_jobs()
    logger.info(f"Loaded {len(existing)} existing jobs, {len(manual)} manual entries")

    # Scrape new jobs from ATS platforms
    scraped = scrape_all_sources()
    logger.info(f"Scraped {len(scraped)} jobs from all sources")

    # Merge: manual → existing → scraped (earliest date wins for dupes)
    all_jobs = merge_jobs([], manual)
    all_jobs = merge_jobs(all_jobs, existing)
    all_jobs = merge_jobs(all_jobs, scraped)
    logger.info(f"Total unique jobs after merge: {len(all_jobs)}")

    # Save (sorts newest-first internally)
    save_jobs(all_jobs)

    logger.info("Scraping complete!")
    return all_jobs


if __name__ == "__main__":
    run()
