"""Scraper for Workday ATS career pages.

Many large banks and financial institutions use Workday.
Workday career pages can be queried via their search API.
"""

import logging
import requests
import json
from typing import List
from datetime import datetime

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role
from datetime import date as _date

logger = logging.getLogger(__name__)

# Companies with Workday career pages
# Format: (tenant, company_name, career_site_path)
WORKDAY_SITES = [
    ("gs", "Goldman Sachs", "goldmansachs"),
    ("morganstanley", "Morgan Stanley", "morganstanley"),
    ("jpmc", "JPMorgan Chase", "jpmorgan"),
    ("bolopp", "Bank of America", "bankofamerica"),
    ("citi", "Citigroup", "citi"),
    ("barclays", "Barclays", "barclays"),
    ("ubs", "UBS", "ubs"),
    ("db", "Deutsche Bank", "deutschebank"),
    ("wellsfargo", "Wells Fargo", "wellsfargo"),
    ("jefferies", "Jefferies", "jefferies"),
    ("lazard", "Lazard", "lazard"),
    ("evercore", "Evercore", "evercore"),
    ("deloitte", "Deloitte", "deloitte"),
    ("pwc", "PwC", "pwcglobal"),
    ("ey", "EY", "eyglobal"),
    ("kpmg", "KPMG", "kpmg"),
    ("mckinsey", "McKinsey & Company", "mckinsey"),
    ("bain", "Bain & Company", "bain"),
    ("bcg", "Boston Consulting Group", "bcg"),
    ("blackrock", "BlackRock", "blackrock"),
    ("vanguard", "Vanguard", "vanguard"),
    ("fidelity", "Fidelity Investments", "fidelity"),
    ("statestreet", "State Street", "statestreet"),
    ("pimco", "PIMCO", "pimco"),
    ("blackstone", "Blackstone", "blackstone"),
    ("kkr", "KKR", "kkr"),
    ("carlyle", "The Carlyle Group", "carlyle"),
    ("tpg", "TPG", "tpg"),
    ("visa", "Visa", "visa"),
    ("mastercard", "Mastercard", "mastercard"),
    ("amex", "American Express", "americanexpress"),
    ("capitalonecareer", "Capital One", "capitalone"),
]


def scrape_workday_site(tenant: str, company_name: str, site_path: str) -> List[Job]:
    """Attempt to scrape a Workday career site.

    Workday sites have varying APIs. This tries common endpoints.
    """
    jobs = []

    # Workday search API endpoint pattern
    search_url = f"https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site_path}/jobs"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; FinanceJobsScraper/1.0)",
    }

    # Search for finance new grad roles
    search_queries = [
        "new grad analyst",
        "analyst program 2026",
        "new graduate finance",
        "campus analyst",
        "entry level analyst",
        "associate program 2026",
        "rotational analyst",
        "investment banking analyst",
        "sales and trading analyst",
    ]

    seen_urls = set()

    for query in search_queries:
        payload = {
            "appliedFacets": {},
            "limit": 20,
            "offset": 0,
            "searchText": query,
        }

        try:
            resp = requests.post(search_url, json=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue

            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.debug(f"Failed query '{query}' for {company_name}: {e}")
            continue

        for posting in data.get("jobPostings", []):
            title = posting.get("title", "")
            external_path = posting.get("externalPath", "")
            posted_on = posting.get("postedOn", "")
            locations = posting.get("locationsText", "")
            bullet_fields = posting.get("bulletFields", [])

            job_url = f"https://{tenant}.wd1.myworkdayjobs.com/{site_path}{external_path}"

            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            # Parse date
            date_posted = ""
            if posted_on:
                try:
                    dt = datetime.strptime(posted_on, "%Y-%m-%dT%H:%M:%S%z")
                    date_posted = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date_posted = posted_on[:10] if len(posted_on) >= 10 else ""

            description = " ".join(bullet_fields) if bullet_fields else ""

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
                location=locations or "United States",
                url=job_url,
                date_posted=date_posted,
                category=category,
                source="workday",
                date_added=_date.today().isoformat(),
            ))

    logger.info(f"Found {len(jobs)} finance new grad jobs at {company_name} (Workday)")
    return jobs


def scrape_all() -> List[Job]:
    """Scrape all known Workday career sites."""
    all_jobs = []
    for tenant, company_name, site_path in WORKDAY_SITES:
        all_jobs.extend(scrape_workday_site(tenant, company_name, site_path))
    return all_jobs
