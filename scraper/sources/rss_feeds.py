"""Scraper for career sites with RSS/Atom feeds.

Covers EY (SuccessFactors/J2W), Evercore (Oleeo/TAL.net), and other
companies that expose job listings via standard RSS or Atom feeds.
"""

import logging
import requests
from typing import List
from datetime import datetime, date
from xml.etree import ElementTree as ET

from scraper.models import Job
from scraper.filters import classify_role, is_new_grad, is_2026_role

logger = logging.getLogger(__name__)

# Format: (feed_url, company_name, feed_type)
# feed_type: "rss" or "atom"
RSS_FEED_SITES = [
    ("https://careers.ey.com/services/rss/job/?locale=en_US&keywords=(analyst+program)", "EY", "rss"),
    ("https://careers.ey.com/services/rss/job/?locale=en_US&keywords=(new+grad)", "EY", "rss"),
    ("https://evercore.tal.net/vx/mobile-0/appcentre-1/brand-5/candidate/jobboard/vacancy/3/feed", "Evercore", "atom"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FinanceJobsScraper/1.0)",
}


def _parse_rss_date(date_str: str) -> str:
    if not date_str:
        return ""
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _parse_atom_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def scrape_rss_feed(feed_url: str, company_name: str) -> List[Job]:
    jobs = []
    today = date.today().isoformat()

    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"RSS {company_name}: {e}")
        return jobs

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.warning(f"RSS {company_name} parse error: {e}")
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

        # Strip UTM params
        if "?" in job_url and "utm_" in job_url:
            job_url = job_url.split("?")[0]

        date_posted = _parse_rss_date(pub_date_el.text if pub_date_el is not None else "")

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
            source="rss_feed",
            date_added=today,
        ))

    return jobs


def scrape_atom_feed(feed_url: str, company_name: str) -> List[Job]:
    jobs = []
    today = date.today().isoformat()
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Atom {company_name}: {e}")
        return jobs

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.warning(f"Atom {company_name} parse error: {e}")
        return jobs

    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        updated_el = entry.find("atom:updated", ns)
        published_el = entry.find("atom:published", ns)

        if title_el is None:
            continue

        title = title_el.text or ""
        job_url = link_el.get("href", "") if link_el is not None else ""
        if not title or not job_url:
            continue

        date_str = (published_el.text if published_el is not None else "") or (updated_el.text if updated_el is not None else "")
        date_posted = _parse_atom_date(date_str)

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
            source="rss_feed",
            date_added=today,
        ))

    return jobs


def scrape_all() -> List[Job]:
    all_jobs = []
    seen_urls = set()

    for feed_url, company_name, feed_type in RSS_FEED_SITES:
        if feed_type == "rss":
            results = scrape_rss_feed(feed_url, company_name)
        else:
            results = scrape_atom_feed(feed_url, company_name)

        for job in results:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)

    if all_jobs:
        logger.info(f"RSS/Atom feeds: {len(all_jobs)} new-grad roles")
    return all_jobs
