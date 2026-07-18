"""Scraper for Oracle HCM Cloud (Oracle Recruiting Cloud) career sites.

Several major banks use Oracle HCM Cloud with a public REST API:
GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
"""

import logging
import requests
from typing import List
from datetime import date

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role, is_entry_level_role, classify_experience

logger = logging.getLogger(__name__)

# Verified Oracle HCM Cloud sites (tested 2026-07-18)
# Format: (host, site_number, company_name)
ORACLE_HCM_SITES = [
    ("jpmc.fa.oraclecloud.com", "CX_1001", "JPMorgan Chase"),
    ("eofe.fa.us2.oraclecloud.com", "CX_3001", "BNY Mellon"),
    ("hdpc.fa.us2.oraclecloud.com", "CX_1002", "Goldman Sachs"),
    ("icbpjb.fa.ocs.oraclecloud.com", "CX_1", "Lazard"),
    ("egug.fa.us2.oraclecloud.com", "CX_1", "American Express"),
]

API_PATH = "/hcmRestApi/resources/latest/recruitingCEJobRequisitions"


def scrape_site(host: str, site_number: str, company_name: str) -> List[Job]:
    jobs = []
    today = date.today().isoformat()
    seen_ids = set()

    for keyword in ["analyst program", "new grad", "2026", "2027", "graduate", "entry level analyst"]:
        url = f"https://{host}{API_PATH}"
        params = {
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations",
            "finder": f"findReqs;siteNumber={site_number},keyword={keyword},limit=25,offset=0,sortBy=POSTING_DATES_DESC",
        }

        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.debug(f"Oracle HCM {company_name} keyword '{keyword}': {e}")
            continue

        items = data.get("items", [])
        if not items:
            continue

        for item in items:
            for req in item.get("requisitionList", []):
                req_id = req.get("Id", "")
                if req_id in seen_ids:
                    continue
                seen_ids.add(req_id)

                title = req.get("Title", "")
                posted_date = req.get("PostedDate", "")
                location = req.get("PrimaryLocation", "")
                country = req.get("PrimaryLocationCountry", "")

                secondary = req.get("secondaryLocations", [])
                if secondary:
                    all_locs = [location] + [s.get("Name", "") for s in secondary if s.get("Name")]
                    location = "; ".join(loc for loc in all_locs if loc)

                job_url = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site_number.replace('CX_', 'CX_')}/job/{req_id}"

                if not is_entry_level_role(title, ""):
                    continue

                category = classify_role(title, "", company_name)
                if not category:
                    continue

                if not is_2026_role(title, "", posted_date):
                    continue

                jobs.append(Job(
                    company=company_name,
                    role=title,
                    location=location or "United States",
                    url=job_url,
                    date_posted=posted_date,
                    category=category,
                    source="oracle_hcm",
                    date_added=today,
                ))

    if jobs:
        logger.info(f"Oracle HCM {company_name}: {len(jobs)} new-grad roles")
    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    for host, site_number, company_name in ORACLE_HCM_SITES:
        all_jobs.extend(scrape_site(host, site_number, company_name))
    return all_jobs
