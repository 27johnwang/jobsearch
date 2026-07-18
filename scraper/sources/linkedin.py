"""Scraper for LinkedIn public job search.

Uses LinkedIn's guest/unauthenticated jobs API which returns HTML cards.
No login or API key required. Rate-limited to be respectful.
"""

import logging
import re
import time
import requests
from typing import Dict, List, Tuple
from datetime import date
from bs4 import BeautifulSoup

from scraper.models import Job
from scraper.filters import classify_role, is_2026_role, is_entry_level_role, classify_experience

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# New grad / campus program queries (2027 class)
NEW_GRAD_QUERIES = [
    "new grad analyst 2027 finance",
    "investment banking analyst 2027",
    "investment banking analyst 2028",
    "sales trading analyst 2027",
    "quantitative analyst new grad",
    "quantitative researcher new grad",
    "quantitative trader new grad",
    "asset management analyst program 2027",
    "corporate finance analyst new grad",
    "consulting analyst 2027",
    "financial analyst rotation program",
    "private equity analyst program",
    "analyst program 2027 full time",
    "graduate program finance 2027",
    "wealth management analyst new grad",
    "fixed income analyst new grad",
    "equity research analyst new grad",
    "fintech analyst new grad 2027",
    "trader new grad 2027",
]

# Entry-level queries (0-2 years experience)
ENTRY_LEVEL_QUERIES = [
    "entry level financial analyst",
    "entry level investment analyst",
    "junior financial analyst",
    "junior investment analyst",
    "FP&A analyst entry level",
    "risk analyst entry level finance",
    "credit analyst entry level",
    "compliance analyst entry level finance",
    "entry level corporate finance analyst",
    "financial analyst 0-2 years",
    "junior quantitative analyst",
    "entry level trading analyst",
    "junior risk analyst",
    "entry level wealth management analyst",
    "analyst I finance",
]

SEARCH_QUERIES = NEW_GRAD_QUERIES + ENTRY_LEVEL_QUERIES

PAGES_PER_QUERY = 3

_TITLE_EXCLUDE_RE = re.compile(
    r"senior\b|sr\.\b|lead\b|principal\b|director\b|"
    r"head\s*of\b|manager\b(?!.*program)|vp\b|vice\s*president|"
    r"(?:5|6|7|8|9|10)\+?\s*years|"
    r"intern\b(?!.*convert)|internship\b|"
    r"summer\s*analyst|summer\s*associate|"
    r"staff\s*(?:engineer|analyst)|"
    r"nurse|teacher|electrician|contractor|coordinator\b|"
    r"travel\s*rn|seasonal\s*retail|substitute\s*teacher",
    re.IGNORECASE,
)


def _parse_card(card) -> dict | None:
    title_el = card.find("h3", class_="base-search-card__title")
    company_el = card.find("h4", class_="base-search-card__subtitle")
    loc_el = card.find("span", class_="job-search-card__location")
    time_el = card.find("time")
    link_el = card.find("a", class_="base-card__full-link")

    if not title_el or not company_el:
        return None

    title = title_el.get_text(strip=True)
    company = company_el.get_text(strip=True)
    location = loc_el.get_text(strip=True) if loc_el else ""
    date_posted = time_el.get("datetime", "") if time_el else ""
    job_url = link_el.get("href", "").split("?")[0] if link_el else ""

    if not job_url:
        return None

    if _TITLE_EXCLUDE_RE.search(title):
        return None

    return {
        "title": title,
        "company": company,
        "location": location,
        "date_posted": date_posted,
        "url": job_url,
    }


def scrape_linkedin() -> List[Job]:
    seen: Dict[Tuple[str, str], dict] = {}
    today = date.today().isoformat()

    for query in SEARCH_QUERIES:
        for page in range(PAGES_PER_QUERY):
            start = page * 10
            params = {
                "keywords": query,
                "location": "United States",
                "f_TPR": "r604800",  # past 7 days
                "f_E": "2",  # entry level
                "start": start,
            }

            try:
                resp = requests.get(
                    SEARCH_URL, params=params, headers=HEADERS, timeout=15
                )
                if resp.status_code != 200 or len(resp.text) < 100:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.find_all("div", class_="base-card")
                if not cards:
                    break

                for card in cards:
                    parsed = _parse_card(card)
                    if not parsed:
                        continue

                    key = (parsed["company"].lower(), parsed["title"].lower())
                    if key not in seen:
                        seen[key] = parsed

            except requests.RequestException as e:
                logger.debug(f"LinkedIn query '{query}' page {page}: {e}")
                break

            time.sleep(1)

    jobs = []
    for data in seen.values():
        category = classify_role(data["title"], "", data["company"])
        if not category:
            continue

        if not is_entry_level_role(data["title"], ""):
            continue

        if not is_2026_role(data["title"], "", data["date_posted"]):
            continue

        exp_type, min_y, max_y = classify_experience(data["title"], "")

        jobs.append(
            Job(
                company=data["company"],
                role=data["title"],
                location=data["location"] or "United States",
                url=data["url"],
                date_posted=data["date_posted"],
                category=category,
                source="linkedin",
                date_added=today,
                experience_type=exp_type,
                min_years=min_y,
                max_years=max_y,
            )
        )

    logger.info(f"LinkedIn: {len(jobs)} finance roles (last 7 days)")
    return jobs


def scrape_all() -> List[Job]:
    return scrape_linkedin()
