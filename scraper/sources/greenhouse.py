"""Scraper for Greenhouse ATS job boards.

Greenhouse provides a public JSON API for company job boards:
https://boards-api.greenhouse.io/v1/boards/{company}/jobs
"""

import logging
import requests
from typing import List
from datetime import datetime, date

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role, is_entry_level_role, classify_experience

logger = logging.getLogger(__name__)

# Verified working Greenhouse boards (tested 2026-07-18)
GREENHOUSE_BOARDS = {
    # FinTech
    "stripe": "Stripe",
    "brex": "Brex",
    "affirm": "Affirm",
    "robinhood": "Robinhood",
    "coinbase": "Coinbase",
    "sofi": "SoFi",
    "chime": "Chime",
    "marqeta": "Marqeta",
    "ripple": "Ripple",
    "block": "Block",
    "figure": "Figure",
    "betterment": "Betterment",
    "nubank": "Nubank",
    "adyen": "Adyen",
    # Quant / Trading
    "point72": "Point72",
    "schonfeld": "Schonfeld",
    "squarepointcapital": "Squarepoint Capital",
    "transmarketgroup": "TransMarket Group",
    "akunacapital": "Akuna Capital",
    "flowtraders": "Flow Traders",
    "aqr": "AQR Capital Management",
    "worldquant": "WorldQuant",
    "janestreet": "Jane Street",
    "imc": "IMC Trading",
    "jumptrading": "Jump Trading",
    "oldmissioncapital": "Old Mission Capital",
    "marshallwace": "Marshall Wace",
    "mangroup": "Man Group",
    # PE / VC
    "generalatlantic": "General Atlantic",
    "a16z": "Andreessen Horowitz",
    # Tech (Fortune 500 / large companies with finance roles)
    "databricks": "Databricks",
    "datadog": "Datadog",
    "mongodb": "MongoDB",
    "okta": "Okta",
    "zscaler": "Zscaler",
    "cloudflare": "Cloudflare",
    "airbnb": "Airbnb",
    "pinterest": "Pinterest",
    "elastic": "Elastic",
    "gitlab": "GitLab",
    "twilio": "Twilio",
    "lyft": "Lyft",
    "dropbox": "Dropbox",
    # Consulting
    "bcg": "BCG",
    # Media
    "disney": "Disney",
    "fox": "Fox Corporation",
}

API_BASE = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def scrape_board(board_slug: str, company_name: str) -> List[Job]:
    jobs = []
    url = API_BASE.format(board=board_slug)

    try:
        resp = requests.get(url, params={"content": "true"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"Greenhouse {board_slug}: {e}")
        return jobs

    for listing in data.get("jobs", []):
        title = listing.get("title", "")
        content = listing.get("content", "")
        location_name = listing.get("location", {}).get("name", "")
        job_url = listing.get("absolute_url", "")
        updated_at = listing.get("updated_at", "")

        date_posted = ""
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                date_posted = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        if not is_entry_level_role(title, content):
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
            date_added=date.today().isoformat(),
        ))

    if jobs:
        logger.info(f"Greenhouse {company_name}: {len(jobs)} new-grad roles")
    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    for board_slug, company_name in GREENHOUSE_BOARDS.items():
        all_jobs.extend(scrape_board(board_slug, company_name))
    return all_jobs
