"""Main scraper orchestrator.

Coordinates scraping from all sources, deduplicates results,
manages freshness (archives stale listings), and saves to JSON.

Jobs older than MAX_AGE_DAYS are removed unless they have no date
(legacy manual entries are kept in a separate archive section).
"""

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from scraper.models import Job
from scraper.filters import _EXCLUSION_RE, classify_experience
from scraper.sources import greenhouse, workday, ashby, simplify, linkedin, oracle_hcm, avature, rss_feeds, smartrecruiters

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
MANUAL_FILE = DATA_DIR / "manual_jobs.json"

MAX_AGE_DAYS = 90


def _job_key(job: Job) -> Tuple[str, str]:
    return (job.company.lower(), job.url.lower().rstrip("/"))


def load_existing_jobs() -> List[Job]:
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
    today = date.today().isoformat()
    by_key: Dict[Tuple[str, str], Job] = {}

    for job in existing:
        key = _job_key(job)
        if key not in by_key:
            by_key[key] = job

    for job in incoming:
        if not job.date_added:
            job.date_added = today

        key = _job_key(job)
        if key in by_key:
            prev = by_key[key]
            if job.date_posted and (not prev.date_posted or job.date_posted < prev.date_posted):
                prev.date_posted = job.date_posted
        else:
            by_key[key] = job

    return list(by_key.values())


def _is_stale(job: Job, cutoff: str) -> bool:
    """A job is stale if its effective date is older than the cutoff."""
    d = job.effective_date
    if not d:
        return False
    return d < cutoff


def prune_stale(jobs: List[Job]) -> List[Job]:
    """Remove jobs older than MAX_AGE_DAYS. Keep undated jobs."""
    cutoff = (date.today() - timedelta(days=MAX_AGE_DAYS)).isoformat()
    fresh = []
    stale_count = 0
    for job in jobs:
        if _is_stale(job, cutoff):
            stale_count += 1
        else:
            fresh.append(job)
    if stale_count:
        logger.info(f"Pruned {stale_count} stale listings (older than {MAX_AGE_DAYS} days)")
    return fresh


def save_jobs(jobs: List[Job]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    jobs.sort(key=lambda j: j.effective_date or "0000-00-00", reverse=True)
    with open(JOBS_FILE, "w") as f:
        json.dump([j.to_dict() for j in jobs], f, indent=2)
    logger.info(f"Saved {len(jobs)} jobs to {JOBS_FILE}")


def scrape_all_sources() -> List[Job]:
    all_jobs = []

    logger.info("Scraping LinkedIn jobs...")
    all_jobs.extend(linkedin.scrape_all())

    logger.info("Scraping Greenhouse boards...")
    all_jobs.extend(greenhouse.scrape_all())

    logger.info("Scraping Workday career sites...")
    all_jobs.extend(workday.scrape_all())

    logger.info("Scraping Oracle HCM Cloud sites...")
    all_jobs.extend(oracle_hcm.scrape_all())

    logger.info("Scraping Ashby boards...")
    all_jobs.extend(ashby.scrape_all())

    logger.info("Scraping Avature career sites...")
    all_jobs.extend(avature.scrape_all())

    logger.info("Scraping RSS/Atom feeds...")
    all_jobs.extend(rss_feeds.scrape_all())

    logger.info("Scraping SmartRecruiters...")
    all_jobs.extend(smartrecruiters.scrape_all())

    logger.info("Scraping SimplifyJobs GitHub...")
    all_jobs.extend(simplify.scrape_all())

    return all_jobs


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting finance new grad job scraper...")

    existing = load_existing_jobs()
    manual = load_manual_jobs()
    logger.info(f"Loaded {len(existing)} existing jobs, {len(manual)} manual entries")

    scraped = scrape_all_sources()
    logger.info(f"Scraped {len(scraped)} jobs from all sources")

    # Merge: manual → existing → scraped
    all_jobs = merge_jobs([], manual)
    all_jobs = merge_jobs(all_jobs, existing)
    all_jobs = merge_jobs(all_jobs, scraped)
    logger.info(f"Total unique jobs after merge: {len(all_jobs)}")

    # Re-validate: remove jobs matching exclusion patterns (summer analysts, interns, senior)
    before = len(all_jobs)
    all_jobs = [j for j in all_jobs if not _EXCLUSION_RE.search(j.role)]
    if len(all_jobs) < before:
        logger.info(f"Excluded {before - len(all_jobs)} jobs (summer analyst/intern/senior)")

    # Classify experience type for all jobs
    for job in all_jobs:
        if job.experience_type == "new_grad" and job.min_years == 0 and job.max_years == 0:
            exp_type, min_y, max_y = classify_experience(job.role, "")
            job.experience_type = exp_type
            job.min_years = min_y
            job.max_years = max_y

    new_grad_count = sum(1 for j in all_jobs if j.experience_type == "new_grad")
    entry_count = sum(1 for j in all_jobs if j.experience_type == "entry_level")
    logger.info(f"Experience split: {new_grad_count} new grad, {entry_count} entry level")

    # Prune stale listings
    all_jobs = prune_stale(all_jobs)

    # Save
    save_jobs(all_jobs)

    dated = sum(1 for j in all_jobs if j.date_posted)
    logger.info(f"Done: {len(all_jobs)} jobs ({dated} with dates)")
    return all_jobs


if __name__ == "__main__":
    run()
