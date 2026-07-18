"""Scraper for Ashby ATS job boards.

Ashby provides a public JSON API:
https://api.ashbyhq.com/posting-api/job-board/{company}
"""

import logging
import requests
from typing import List
from datetime import datetime, date

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role, is_entry_level_role, classify_experience

logger = logging.getLogger(__name__)

# Verified working Ashby boards (tested 2026-07-18)
ASHBY_BOARDS = {
    # FinTech / Finance
    "ramp": "Ramp",
    "plaid": "Plaid",
    "rho": "Rho",
    "wealthsimple": "Wealthsimple",
    "acorns": "Acorns",
    "column": "Column",
    "lemonade": "Lemonade",
    "middesk": "Middesk",
    "persona": "Persona",
    "watershed": "Watershed",
    "zip": "Zip",
    "clearco": "Clearco",
    "snapdocs": "Snapdocs",
    # Tech (may have finance roles)
    "notion": "Notion",
    "openai": "OpenAI",
    "cohere": "Cohere",
    "linear": "Linear",
    "vanta": "Vanta",
    "confluent": "Confluent",
    "drata": "Drata",
    "benchling": "Benchling",
    "amplitude": "Amplitude",
    "zapier": "Zapier",
    "weave": "Weave",
}

API_BASE = "https://api.ashbyhq.com/posting-api/job-board/{company}"


def scrape_board(board_slug: str, company_name: str) -> List[Job]:
    jobs = []
    url = API_BASE.format(company=board_slug)

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"Ashby {board_slug}: {e}")
        return jobs

    for listing in data.get("jobs", []):
        title = listing.get("title", "")
        description = listing.get("descriptionPlain", "")
        location = listing.get("location", "")
        job_url = listing.get("jobUrl", "")
        published_at = listing.get("publishedAt", "")

        date_posted = ""
        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                date_posted = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        secondary = listing.get("secondaryLocations", [])
        if secondary:
            all_locs = [location] + [s.get("location", "") for s in secondary]
            location = "; ".join(loc for loc in all_locs if loc)

        if not is_entry_level_role(title, description):
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
            source="ashby",
            date_added=date.today().isoformat(),
        ))

    if jobs:
        logger.info(f"Ashby {company_name}: {len(jobs)} new-grad roles")
    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    for board_slug, company_name in ASHBY_BOARDS.items():
        all_jobs.extend(scrape_board(board_slug, company_name))
    return all_jobs
