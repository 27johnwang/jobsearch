"""Scraper for SmartRecruiters ATS.

SmartRecruiters provides a fully public REST API:
https://api.smartrecruiters.com/v1/companies/{id}/postings
"""

import logging
import requests
from typing import List
from datetime import datetime, date

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role

logger = logging.getLogger(__name__)

# Verified SmartRecruiters company IDs (tested 2026-07-18)
SMARTRECRUITERS_COMPANIES = {
    "Visa": "Visa",
    "Palantir": "Palantir Technologies",
}

API_BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
PAGE_SIZE = 100


def scrape_company(company_id: str, company_name: str) -> List[Job]:
    jobs = []
    today = date.today().isoformat()
    seen_ids = set()
    offset = 0

    while True:
        url = API_BASE.format(company=company_id)
        params = {"limit": PAGE_SIZE, "offset": offset}

        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                break
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.debug(f"SmartRecruiters {company_name}: {e}")
            break

        postings = data.get("content", [])
        if not postings:
            break

        for posting in postings:
            posting_id = posting.get("id", "")
            if posting_id in seen_ids:
                continue
            seen_ids.add(posting_id)

            title = posting.get("name", "")
            released = posting.get("releasedDate", "")
            location = posting.get("location", {})
            loc_city = location.get("city", "")
            loc_region = location.get("region", "")
            loc_country = location.get("country", "")
            loc_str = ", ".join(p for p in [loc_city, loc_region, loc_country] if p)

            ref_url = posting.get("ref", "")
            company_info = posting.get("company", {})
            actual_name = company_info.get("name", company_name)

            date_posted = ""
            if released:
                try:
                    dt = datetime.fromisoformat(released.replace("Z", "+00:00"))
                    date_posted = dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            if not is_new_grad(title, ""):
                continue

            category = classify_role(title, "", actual_name)
            if not category:
                continue

            if not is_2026_role(title, "", date_posted):
                continue

            job_url = ref_url or f"https://jobs.smartrecruiters.com/{company_id}/{posting_id}"

            jobs.append(Job(
                company=actual_name,
                role=title,
                location=loc_str or "United States",
                url=job_url,
                date_posted=date_posted,
                category=category,
                source="smartrecruiters",
                date_added=today,
            ))

        total = data.get("totalFound", 0)
        offset += PAGE_SIZE
        if offset >= total:
            break

    if jobs:
        logger.info(f"SmartRecruiters {company_name}: {len(jobs)} new-grad roles")
    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    for company_id, company_name in SMARTRECRUITERS_COMPANIES.items():
        all_jobs.extend(scrape_company(company_id, company_name))
    return all_jobs
