"""Scraper for Avature ATS career sites via RSS feeds.

Avature provides RSS feeds at:
https://{host}/{portal}/SearchJobs/feed/
or
https://{host}/{portal}/SearchJobs/data/feed/
"""

import logging
import requests
from typing import List
from datetime import datetime, date
from xml.etree import ElementTree as ET

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role

logger = logging.getLogger(__name__)

# Verified Avature career sites (tested 2026-07-18)
# Format: (feed_url, company_name, record_type)
# record_type: "job" uses jobRecordsPerPage, "folder" uses folderRecordsPerPage
AVATURE_SITES = [
    ("https://careers.bain.com/jobs/SearchJobs/feed/", "Bain & Company", "folder"),
    ("https://bloomberg.avature.net/careers/SearchJobs/feed/", "Bloomberg", "job"),
    ("https://apply.deloitte.com/en_US/careers/SearchJobs/feed/", "Deloitte", "job"),
    ("https://koch.avature.net/careers/SearchJobs/feed/", "Koch Industries", "job"),
    ("https://ally.avature.net/careers/SearchJobs/feed/", "Ally Financial", "job"),
]

MAX_RECORDS = 100


def scrape_site(feed_url: str, company_name: str, record_type: str) -> List[Job]:
    jobs = []
    today = date.today().isoformat()
    seen_urls = set()

    param_key = "folderRecordsPerPage" if record_type == "folder" else "jobRecordsPerPage"
    url = f"{feed_url}?{param_key}={MAX_RECORDS}"

    try:
        resp = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FinanceJobsScraper/1.0)",
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Avature {company_name}: {e}")
        return jobs

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.warning(f"Avature {company_name} XML parse error: {e}")
        return jobs

    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")

        if title_el is None or link_el is None:
            continue

        title = title_el.text or ""
        job_url = link_el.text or ""

        if not title or not job_url:
            continue

        if job_url in seen_urls:
            continue
        seen_urls.add(job_url)

        date_posted = ""
        if pub_date_el is not None and pub_date_el.text:
            try:
                dt = datetime.strptime(pub_date_el.text.strip(), "%a, %d %b %Y %H:%M:%S %z")
                date_posted = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        if not is_new_grad(title, ""):
            continue

        category = classify_role(title, "", company_name)
        if not category:
            continue

        if not is_2026_role(title, "", date_posted):
            continue

        jobs.append(Job(
            company=company_name,
            role=title,
            location="United States",
            url=job_url,
            date_posted=date_posted,
            category=category,
            source="avature",
            date_added=today,
        ))

    if jobs:
        logger.info(f"Avature {company_name}: {len(jobs)} new-grad roles")
    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    for feed_url, company_name, record_type in AVATURE_SITES:
        all_jobs.extend(scrape_site(feed_url, company_name, record_type))
    return all_jobs
