"""Scraper for Greenhouse ATS job boards.

Greenhouse provides a public JSON API for company job boards:
https://boards-api.greenhouse.io/v1/boards/{company}/jobs
"""

import logging
import requests
from typing import List
from datetime import datetime

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role

logger = logging.getLogger(__name__)

# Companies with Greenhouse boards that have finance new grad roles
GREENHOUSE_BOARDS = {
    # FinTech
    "stripe": "Stripe",
    "plaid": "Plaid",
    "brex": "Brex",
    "affirm": "Affirm",
    "robinhood": "Robinhood",
    "sofi": "SoFi",
    "coinbase": "Coinbase",
    "chime": "Chime",
    "marqeta": "Marqeta",
    "ripple": "Ripple",
    "circle": "Circle",
    # Asset Management / Quant
    "twosigma": "Two Sigma",
    "deshaw": "D.E. Shaw",
    "citadel": "Citadel",
    "point72": "Point72",
    "bridgewater": "Bridgewater Associates",
    "millenniummanagement": "Millennium Management",
    "aresmanagement": "Ares Management",
    # Consulting
    "oliverwyman": "Oliver Wyman",
    "alvarezandmarsal": "Alvarez & Marsal",
    # Market Data / Infrastructure
    "bloomberg": "Bloomberg",
    "msci": "MSCI",
    "pitchbook": "PitchBook",
    "factset": "FactSet",
    "morningstar": "Morningstar",
    "spglobal": "S&P Global",
    # Exchanges
    "cmegroup": "CME Group",
    "cboe": "Cboe Global Markets",
    # PE / VC
    "generalatlantic": "General Atlantic",
    "thomabravo": "Thoma Bravo",
    "sequoiacap": "Sequoia Capital",
    "a16z": "Andreessen Horowitz",
    # Insurance / Financial Services
    "capitalone": "Capital One",
}

API_BASE = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def scrape_board(board_slug: str, company_name: str) -> List[Job]:
    """Scrape a single Greenhouse board for finance new grad jobs."""
    jobs = []
    url = API_BASE.format(board=board_slug)

    try:
        resp = requests.get(url, params={"content": "true"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch Greenhouse board {board_slug}: {e}")
        return jobs

    for listing in data.get("jobs", []):
        title = listing.get("title", "")
        content = listing.get("content", "")
        location_name = listing.get("location", {}).get("name", "")
        job_url = listing.get("absolute_url", "")
        updated_at = listing.get("updated_at", "")

        # Parse date
        date_posted = ""
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                date_posted = dt.strftime("%Y-%m-%d")
            except ValueError:
                date_posted = ""

        # Filter: must be new grad and finance-related
        if not is_new_grad(title, content):
            continue

        category = classify_role(title, content, company_name)
        if not category:
            continue

        if not is_2026_role(title, content, date_posted):
            continue

        jobs.append(Job(
            company=company_name,
            role=title,
            location=location_name or "United States",
            url=job_url,
            date_posted=date_posted,
            category=category,
            source="greenhouse",
        ))

    logger.info(f"Found {len(jobs)} finance new grad jobs at {company_name} (Greenhouse)")
    return jobs


def scrape_all() -> List[Job]:
    """Scrape all known Greenhouse boards."""
    all_jobs = []
    for board_slug, company_name in GREENHOUSE_BOARDS.items():
        all_jobs.extend(scrape_board(board_slug, company_name))
    return all_jobs
