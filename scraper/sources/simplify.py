"""Scraper for SimplifyJobs/New-Grad-Positions GitHub repository.

Parses the markdown tables from their README using BeautifulSoup to
extract finance-related new-grad positions.
"""

import logging
import re
import requests
from typing import List
from datetime import date, timedelta
from bs4 import BeautifulSoup

from scraper.models import Job
from scraper.filters import classify_role, is_2026_role

logger = logging.getLogger(__name__)

README_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"

_AGE_RE = re.compile(r"(\d+)(d|w|mo)")
_EMOJI_RE = re.compile(r"[\U0001f300-\U0001f9ff\U00002600-\U000027bf\U0001fa00-\U0001faff\U0000fe00-\U0000feff\U0001f000-\U0001f02f]+")


def _age_to_date(age_str: str) -> str:
    age_str = age_str.strip()
    m = _AGE_RE.match(age_str)
    if not m:
        return ""
    value, unit = int(m.group(1)), m.group(2)
    today = date.today()
    if unit == "d":
        return (today - timedelta(days=value)).isoformat()
    elif unit == "w":
        return (today - timedelta(weeks=value)).isoformat()
    elif unit == "mo":
        return (today - timedelta(days=value * 30)).isoformat()
    return ""


def _clean_company(text: str) -> str:
    text = _EMOJI_RE.sub("", text).strip()
    return text


def scrape_simplify() -> List[Job]:
    jobs = []
    try:
        resp = requests.get(README_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        text = resp.text
    except requests.RequestException as e:
        logger.warning(f"SimplifyJobs fetch failed: {e}")
        return jobs

    # Remove "Inactive roles" detail blocks before parsing
    text = re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)

    soup = BeautifulSoup(text, "html.parser")
    today = date.today().isoformat()
    seen_urls = set()

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            # Cell 0: Company name (inside <strong><a>)
            company_cell = cells[0]
            company_link = company_cell.find("a")
            company = _clean_company(company_link.get_text() if company_link else company_cell.get_text())
            if not company:
                continue

            # Cell 1: Role
            role = cells[1].get_text(strip=True)

            # Cell 2: Location
            location = cells[2].get_text(separator="; ", strip=True)

            # Cell 3: Application link
            apply_cell = cells[3]
            if "🔒" in apply_cell.get_text():
                continue
            apply_link = apply_cell.find("a")
            if not apply_link:
                continue
            apply_url = apply_link.get("href", "")
            if not apply_url:
                continue

            # Strip Simplify tracking params
            apply_url = re.sub(r"[&?]utm_source=Simplify.*$", "", apply_url)
            apply_url = re.sub(r"[&?]ref=Simplify.*$", "", apply_url)

            # Cell 4: Age
            age = cells[4].get_text(strip=True)
            date_posted = _age_to_date(age)

            # Only last 14 days
            if date_posted:
                try:
                    days_old = (date.today() - date.fromisoformat(date_posted)).days
                    if days_old > 14:
                        continue
                except ValueError:
                    pass

            # Dedup within this scrape
            if apply_url in seen_urls:
                continue
            seen_urls.add(apply_url)

            category = classify_role(role, "", company)
            if not category:
                continue

            if not is_2026_role(role, "", date_posted):
                continue

            jobs.append(Job(
                company=company,
                role=role,
                location=location or "United States",
                url=apply_url,
                date_posted=date_posted,
                category=category,
                source="simplify",
                date_added=today,
            ))

    if jobs:
        logger.info(f"SimplifyJobs: {len(jobs)} finance new-grad roles (last 14 days)")
    else:
        logger.info("SimplifyJobs: 0 finance new-grad roles matched")
    return jobs


def scrape_all() -> List[Job]:
    return scrape_simplify()
