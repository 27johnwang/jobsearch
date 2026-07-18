"""Scraper for Workday ATS career pages.

Many large banks and financial institutions use Workday.
Each company has a unique combination of tenant, wd version, and site path.
"""

import logging
import requests
import json
from typing import List
from datetime import datetime, date
import re

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role

logger = logging.getLogger(__name__)

# Verified working Workday sites (tested 2026-07-18)
# Format: (base_url, company_name)
WORKDAY_SITES = [
    # Banks
    ("https://barclays.wd3.myworkdayjobs.com/wday/cxs/barclays/External_Career_Site_Barclays/jobs", "Barclays"),
    ("https://db.wd3.myworkdayjobs.com/wday/cxs/db/DBWebsite/jobs", "Deutsche Bank"),
    ("https://statestreet.wd1.myworkdayjobs.com/wday/cxs/statestreet/Global/jobs", "State Street"),
    ("https://citi.wd5.myworkdayjobs.com/wday/cxs/citi/2/jobs", "Citigroup"),
    ("https://ms.wd5.myworkdayjobs.com/wday/cxs/ms/External/jobs", "Morgan Stanley"),
    ("https://cibc.wd3.myworkdayjobs.com/wday/cxs/cibc/Campus/jobs", "CIBC"),
    # Financial Services
    ("https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers/jobs", "Mastercard"),
    ("https://troweprice.wd5.myworkdayjobs.com/wday/cxs/troweprice/TRowePrice/jobs", "T. Rowe Price"),
    ("https://blackstone.wd1.myworkdayjobs.com/wday/cxs/blackstone/Blackstone_Careers/jobs", "Blackstone"),
    # Investment Banking
    ("https://hl.wd1.myworkdayjobs.com/wday/cxs/hl/External/jobs", "Houlihan Lokey"),
    # Consulting
    ("https://guidehouse.wd1.myworkdayjobs.com/wday/cxs/guidehouse/External/jobs", "Guidehouse"),
    ("https://pwc.wd3.myworkdayjobs.com/wday/cxs/pwc/Global_Experienced_Careers/jobs", "PwC"),
    # Other
    ("https://globalfoundries.wd1.myworkdayjobs.com/wday/cxs/globalfoundries/External/jobs", "GlobalFoundries"),
    ("https://cat.wd5.myworkdayjobs.com/wday/cxs/cat/CaterpillarCareers/jobs", "Caterpillar"),
]

SEARCH_QUERIES = [
    "2026 analyst program",
    "2026 graduate",
    "2027 analyst program",
    "2027 graduate",
    "new grad analyst",
    "new graduate finance",
    "campus analyst 2026",
    "entry level analyst program",
    "rotational analyst program",
]

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; FinanceJobsScraper/1.0)",
}

_POSTED_AGO_RE = re.compile(r"Posted (\d+) Days? Ago", re.IGNORECASE)
_POSTED_TODAY_RE = re.compile(r"Posted Today", re.IGNORECASE)
_POSTED_YESTERDAY_RE = re.compile(r"Posted Yesterday", re.IGNORECASE)


def _parse_posted_on(posted_on: str) -> str:
    if not posted_on:
        return ""
    # Try ISO format first
    try:
        dt = datetime.strptime(posted_on, "%Y-%m-%dT%H:%M:%S%z")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    if len(posted_on) >= 10 and posted_on[4] == "-":
        return posted_on[:10]
    # Workday often returns "Posted X Days Ago" text
    today = date.today()
    if _POSTED_TODAY_RE.search(posted_on):
        return today.isoformat()
    if _POSTED_YESTERDAY_RE.search(posted_on):
        from datetime import timedelta
        return (today - timedelta(days=1)).isoformat()
    m = _POSTED_AGO_RE.search(posted_on)
    if m:
        from datetime import timedelta
        days = int(m.group(1))
        return (today - timedelta(days=days)).isoformat()
    return ""


def scrape_workday_site(api_url: str, company_name: str) -> List[Job]:
    jobs = []
    seen_urls = set()

    # Extract the base URL for building job links
    # e.g. https://barclays.wd3.myworkdayjobs.com/wday/cxs/barclays/External_Career_Site_Barclays/jobs
    # Job URL base: https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays
    parts = api_url.split("/wday/cxs/")
    if len(parts) == 2:
        host = parts[0]
        rest = parts[1]  # e.g. barclays/External_Career_Site_Barclays/jobs
        site_path = rest.split("/")[1]  # e.g. External_Career_Site_Barclays
        job_url_base = f"{host}/{site_path}"
    else:
        job_url_base = api_url.rsplit("/jobs", 1)[0]

    for query in SEARCH_QUERIES:
        payload = {
            "appliedFacets": {},
            "limit": 20,
            "offset": 0,
            "searchText": query,
        }

        try:
            resp = requests.post(api_url, json=payload, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.debug(f"Workday {company_name} query '{query}': {e}")
            continue

        for posting in data.get("jobPostings", []):
            title = posting.get("title", "")
            external_path = posting.get("externalPath", "")
            posted_on = posting.get("postedOn", "")
            locations = posting.get("locationsText", "")
            bullet_fields = posting.get("bulletFields", [])

            job_url = f"{job_url_base}{external_path}"

            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            date_posted = _parse_posted_on(posted_on)
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
                date_added=date.today().isoformat(),
            ))

    if jobs:
        logger.info(f"Workday {company_name}: {len(jobs)} new-grad roles")
    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    for api_url, company_name in WORKDAY_SITES:
        all_jobs.extend(scrape_workday_site(api_url, company_name))
    return all_jobs
