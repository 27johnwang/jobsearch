"""Scraper for Lever ATS job boards.

Lever provides a public JSON API for company job boards:
https://api.lever.co/v0/postings/{company}
"""

import logging
import requests
from typing import List
from datetime import datetime

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role
from datetime import date as _date

logger = logging.getLogger(__name__)

# Companies with Lever boards that have finance new grad roles
LEVER_BOARDS = {
    # FinTech
    "wise": "Wise",
    "checkout": "Checkout.com",
    "adyen": "Adyen",
    # Quant / Trading
    "imc": "IMC Trading",
    "drweng": "DRW",
    "oldmissioncapital": "Old Mission Capital",
    "hudsonrivertrading": "Hudson River Trading",
    "akuna": "Akuna Capital",
    "optiver": "Optiver",
    "susquehanna": "Susquehanna International Group (SIG)",
    "janestreet": "Jane Street",
    "fiverings": "Five Rings",
    "jumptrading": "Jump Trading",
    # PE / VC / AM
    "silverlake": "Silver Lake",
    "wellingtonmanagement": "Wellington Management",
    # Other Financial
    "moodys": "Moody's",
}

API_BASE = "https://api.lever.co/v0/postings/{company}"


def scrape_board(board_slug: str, company_name: str) -> List[Job]:
    """Scrape a single Lever board for finance new grad jobs."""
    jobs = []
    url = API_BASE.format(company=board_slug)

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch Lever board {board_slug}: {e}")
        return jobs

    if not isinstance(data, list):
        return jobs

    for listing in data:
        title = listing.get("text", "")
        description = listing.get("descriptionPlain", "")
        categories = listing.get("categories", {})
        location = categories.get("location", "")
        job_url = listing.get("hostedUrl", "")
        created_at = listing.get("createdAt", 0)

        # Parse date from timestamp (ms)
        date_posted = ""
        if created_at:
            try:
                dt = datetime.fromtimestamp(created_at / 1000)
                date_posted = dt.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                date_posted = ""

        # Filter
        if not is_new_grad(title, description):
            continue

        category = classify_role(title, description, company_name)
        if not category:
            continue

        if not is_2026_role(title, description, date_posted):
            continue

        jobs.append(Job(
            company=company_name,
            role=title,
            location=location or "United States",
            url=job_url,
            date_posted=date_posted,
            category=category,
            source="lever",
            date_added=_date.today().isoformat(),
        ))

    logger.info(f"Found {len(jobs)} finance new grad jobs at {company_name} (Lever)")
    return jobs


def scrape_all() -> List[Job]:
    """Scrape all known Lever boards."""
    all_jobs = []
    for board_slug, company_name in LEVER_BOARDS.items():
        all_jobs.extend(scrape_board(board_slug, company_name))
    return all_jobs
