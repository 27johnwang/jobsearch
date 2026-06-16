"""Generate README.md from job data, matching SimplifyJobs format."""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List

from scraper.models import Job

DATA_DIR = Path(__file__).parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
README_PATH = Path(__file__).parent.parent / "README.md"

CATEGORY_CONFIG = {
    "Investment Banking": {"emoji": "🏦", "order": 1},
    "Sales & Trading": {"emoji": "📊", "order": 2},
    "Consulting": {"emoji": "💼", "order": 3},
    "Asset Management": {"emoji": "📈", "order": 4},
    "Quantitative Finance": {"emoji": "🔢", "order": 5},
    "Corporate Finance": {"emoji": "🏢", "order": 6},
    "Risk Management": {"emoji": "🛡️", "order": 7},
    "Financial Technology": {"emoji": "💻", "order": 8},
    "Product Management (Finance)": {"emoji": "📱", "order": 9},
    "Sales (Financial Services)": {"emoji": "🤝", "order": 10},
}


def _age_display(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        posted = date.fromisoformat(date_str)
        days = (date.today() - posted).days
        if days < 0:
            return "0d"
        if days == 0:
            return "0d"
        if days < 7:
            return f"{days}d"
        if days < 30:
            return f"{days // 7}w"
        return f"{days // 30}mo"
    except (ValueError, TypeError):
        return ""


def load_jobs() -> List[Job]:
    if not JOBS_FILE.exists():
        return []
    with open(JOBS_FILE, "r") as f:
        data = json.load(f)
    return [Job.from_dict(j) for j in data]


def group_by_category(jobs: List[Job]) -> Dict[str, List[Job]]:
    groups: Dict[str, List[Job]] = {}
    for job in jobs:
        cat = job.category
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(job)
    return groups


def format_location(location: str) -> str:
    locations = [loc.strip() for loc in location.split(";") if loc.strip()]
    if len(locations) <= 2:
        return "</br>".join(locations)
    first = locations[0]
    rest = "</br>".join(locations[1:])
    return (
        f'<details><summary>{first} (+{len(locations)-1} more)</summary>'
        f'{rest}</details>'
    )


def generate_job_row(job: Job) -> str:
    indicators = ""
    if job.is_closed:
        indicators += " 🔒"
    if not job.requires_visa_sponsorship:
        indicators += " 🛂"
    if job.us_citizenship_required:
        indicators += " 🇺🇸"

    company_display = f"**{job.company}**{indicators}"

    if job.is_closed:
        apply_link = "🔒"
    else:
        apply_link = (
            f'<div align="center">'
            f'<a href="{job.url}">'
            f'<img src="https://i.imgur.com/fbjwDvo.png" width="52" alt="Apply">'
            f'</a></div>'
        )

    location = format_location(job.location)

    age = _age_display(job.date_posted)

    return (
        f"<tr>\n"
        f"<td>{company_display}</td>\n"
        f"<td>{job.role}</td>\n"
        f"<td>{location}</td>\n"
        f"<td>{apply_link}</td>\n"
        f"<td>{age}</td>\n"
        f"</tr>"
    )


def generate_category_section(category: str, jobs: List[Job]) -> str:
    config = CATEGORY_CONFIG.get(category, {"emoji": "💰", "order": 99})
    emoji = config["emoji"]

    open_dated = sorted((j for j in jobs if not j.is_closed and j.date_posted),
                        key=lambda j: j.date_posted, reverse=True)
    open_undated = [j for j in jobs if not j.is_closed and not j.date_posted]
    closed_jobs = sorted((j for j in jobs if j.is_closed),
                         key=lambda j: j.effective_date or "", reverse=True)
    jobs[:] = open_dated + open_undated + closed_jobs

    rows = "\n".join(generate_job_row(job) for job in jobs)
    open_count = sum(1 for j in jobs if not j.is_closed)

    return f"""
## {emoji} {category} ({open_count} open)

<table>
<tr>
<th>Company</th>
<th>Role</th>
<th>Location</th>
<th>Application</th>
<th>Age</th>
</tr>
{rows}
</table>
"""


def generate_readme(jobs: List[Job]) -> str:
    total = len(jobs)
    open_count = sum(1 for j in jobs if not j.is_closed)
    groups = group_by_category(jobs)

    sorted_categories = sorted(
        groups.keys(),
        key=lambda c: CATEGORY_CONFIG.get(c, {"order": 99})["order"]
    )

    category_stats = []
    for cat in sorted_categories:
        config = CATEGORY_CONFIG.get(cat, {"emoji": "💰"})
        count = sum(1 for j in groups[cat] if not j.is_closed)
        category_stats.append(f"{config['emoji']} {cat}: {count}")

    stats_str = " | ".join(category_stats)

    toc_entries = []
    for cat in sorted_categories:
        config = CATEGORY_CONFIG.get(cat, {"emoji": "💰"})
        anchor = cat.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("&", "")
        open_in_cat = sum(1 for j in groups[cat] if not j.is_closed)
        toc_entries.append(f"- [{config['emoji']} {cat} ({open_in_cat})](#{anchor}-{open_in_cat}-open)")

    toc = "\n".join(toc_entries)

    sections = "\n".join(
        generate_category_section(cat, groups[cat])
        for cat in sorted_categories
    )

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    readme = f"""# 2026 New Grad Finance Positions 💰

> A daily-updated list of **{open_count}+ open** new graduate positions in finance for the Class of 2026.
>
> Scraped daily from Greenhouse, Workday, Ashby ATS platforms and SimplifyJobs. Newest listings first.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🔒 | Application closed |
| 🛂 | Does not sponsor work visa |
| 🇺🇸 | Requires U.S. citizenship |

**Age key:** 0d = today, 1d = yesterday, 1w = 1 week ago, 1mo = 1 month ago

---

## How to Contribute

Found a role that's missing? Please [open an issue](../../issues) or submit a pull request!

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Categories

{toc}

---

**Total listings: {total}** | **Open: {open_count}**

{stats_str}

---
{sections}

---

<div align="center">

**Last updated: {now}**

This list is updated daily via automated scrapers (Greenhouse, Workday, Ashby, SimplifyJobs) + community contributions.

Star this repo to get notified of updates!

</div>
"""
    return readme


def run():
    jobs = load_jobs()
    readme_content = generate_readme(jobs)
    with open(README_PATH, "w") as f:
        f.write(readme_content)
    print(f"Generated README.md with {len(jobs)} job listings")


if __name__ == "__main__":
    run()
