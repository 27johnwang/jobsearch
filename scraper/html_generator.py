"""Generate an interactive HTML page with experience-level filtering."""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from scraper.models import Job

DATA_DIR = Path(__file__).parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
HTML_PATH = Path(__file__).parent.parent / "jobs.html"


def load_jobs() -> List[Job]:
    if not JOBS_FILE.exists():
        return []
    with open(JOBS_FILE, "r") as f:
        data = json.load(f)
    return [Job.from_dict(j) for j in data]


def generate_html(jobs: List[Job]) -> str:
    jobs_data = []
    for j in jobs:
        jobs_data.append({
            "company": j.company,
            "role": j.role,
            "location": j.location,
            "url": j.url,
            "date_posted": j.date_posted,
            "category": j.category,
            "is_closed": j.is_closed,
            "experience_type": j.experience_type,
            "min_years": j.min_years,
            "max_years": j.max_years,
        })

    jobs_json = json.dumps(jobs_data)
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Jobs Tracker — Interactive</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; line-height: 1.5; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #f0f6fc; margin-bottom: 8px; font-size: 1.8rem; }}
.subtitle {{ color: #8b949e; margin-bottom: 24px; }}
.controls {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
.control-row {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }}
.control-group {{ display: flex; flex-direction: column; gap: 6px; }}
.control-group label {{ font-size: 0.85rem; color: #8b949e; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
.tabs {{ display: flex; gap: 4px; background: #21262d; border-radius: 6px; padding: 3px; }}
.tab {{ padding: 8px 16px; border: none; background: transparent; color: #8b949e; border-radius: 4px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.15s; }}
.tab.active {{ background: #388bfd; color: #fff; }}
.tab:hover:not(.active) {{ background: #30363d; color: #c9d1d9; }}
.yoe-picker {{ display: flex; gap: 4px; background: #21262d; border-radius: 6px; padding: 3px; }}
.yoe-btn {{ padding: 8px 14px; border: none; background: transparent; color: #8b949e; border-radius: 4px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.15s; }}
.yoe-btn.active {{ background: #238636; color: #fff; }}
.yoe-btn:hover:not(.active) {{ background: #30363d; color: #c9d1d9; }}
.category-select {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; }}
.search-input {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; min-width: 200px; }}
.search-input::placeholder {{ color: #484f58; }}
.stats {{ display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }}
.stat {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px 16px; }}
.stat-number {{ font-size: 1.4rem; font-weight: 700; color: #f0f6fc; }}
.stat-label {{ font-size: 0.8rem; color: #8b949e; }}
table {{ width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
thead th {{ background: #21262d; padding: 12px 16px; text-align: left; font-size: 0.85rem; color: #8b949e; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; border-bottom: 1px solid #30363d; }}
tbody td {{ padding: 10px 16px; border-bottom: 1px solid #21262d; font-size: 0.9rem; }}
tbody tr:hover {{ background: #1c2128; }}
.company {{ font-weight: 600; color: #f0f6fc; }}
.role {{ color: #c9d1d9; }}
.location {{ color: #8b949e; font-size: 0.85rem; }}
.apply-btn {{ display: inline-block; padding: 4px 12px; background: #238636; color: #fff; text-decoration: none; border-radius: 4px; font-size: 0.8rem; font-weight: 500; }}
.apply-btn:hover {{ background: #2ea043; }}
.closed {{ color: #f85149; font-size: 0.8rem; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 500; margin-left: 6px; }}
.badge-ng {{ background: #1f6feb33; color: #58a6ff; }}
.badge-el {{ background: #23863633; color: #3fb950; }}
.age {{ color: #8b949e; font-size: 0.85rem; }}
.empty-state {{ text-align: center; padding: 60px 20px; color: #8b949e; }}
.footer {{ text-align: center; padding: 24px; color: #484f58; font-size: 0.85rem; margin-top: 24px; }}
.table-container {{ overflow-x: auto; border-radius: 8px; }}
@media (max-width: 768px) {{
    .control-row {{ flex-direction: column; align-items: stretch; }}
    .search-input {{ min-width: unset; width: 100%; }}
    table {{ font-size: 0.8rem; }}
    thead th, tbody td {{ padding: 8px; }}
}}
</style>
</head>
<body>
<div class="container">
<h1>Finance Jobs Tracker 💰</h1>
<p class="subtitle">Updated {now} — Filter by experience level to find roles that match you</p>

<div class="controls">
<div class="control-row">
<div class="control-group">
<label>Job Type</label>
<div class="tabs">
<button class="tab active" data-tier="all">All</button>
<button class="tab" data-tier="new_grad">🎓 New Grad 2027</button>
<button class="tab" data-tier="entry_level">💼 Entry Level</button>
</div>
</div>
<div class="control-group" id="yoe-group" style="display:none;">
<label>Years of Experience</label>
<div class="yoe-picker">
<button class="yoe-btn active" data-yoe="all">All (0-2)</button>
<button class="yoe-btn" data-yoe="0">0 years</button>
<button class="yoe-btn" data-yoe="1">1 year</button>
<button class="yoe-btn" data-yoe="2">2 years</button>
</div>
</div>
<div class="control-group">
<label>Category</label>
<select class="category-select" id="category-filter">
<option value="all">All Categories</option>
</select>
</div>
<div class="control-group">
<label>Search</label>
<input type="text" class="search-input" id="search-input" placeholder="Company or role...">
</div>
</div>
</div>

<div class="stats" id="stats"></div>

<div class="table-container">
<table>
<thead>
<tr>
<th>Company</th>
<th>Role</th>
<th>Location</th>
<th>Type</th>
<th>Age</th>
<th>Apply</th>
</tr>
</thead>
<tbody id="jobs-table"></tbody>
</table>
</div>
<div class="empty-state" id="empty-state" style="display:none;">No jobs match your filters.</div>

<div class="footer">
Scraped daily from 107+ ATS endpoints across 10 platforms. Star the repo for updates!
</div>
</div>

<script>
const JOBS = {jobs_json};

let currentTier = 'all';
let currentYoe = 'all';
let currentCategory = 'all';
let searchText = '';

function ageDisplay(dateStr) {{
    if (!dateStr) return '';
    const posted = new Date(dateStr + 'T00:00:00');
    const now = new Date();
    const days = Math.floor((now - posted) / 86400000);
    if (days < 0) return '0d';
    if (days === 0) return '0d';
    if (days < 7) return days + 'd';
    if (days < 30) return Math.floor(days/7) + 'w';
    return Math.floor(days/30) + 'mo';
}}

function populateCategories() {{
    const cats = [...new Set(JOBS.map(j => j.category))].sort();
    const sel = document.getElementById('category-filter');
    cats.forEach(c => {{
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        sel.appendChild(opt);
    }});
}}

function filterJobs() {{
    return JOBS.filter(j => {{
        if (currentTier !== 'all' && j.experience_type !== currentTier) return false;
        if (currentTier === 'entry_level' && currentYoe !== 'all') {{
            const yoe = parseInt(currentYoe);
            if (yoe < j.min_years || yoe > j.max_years) return false;
        }}
        if (currentCategory !== 'all' && j.category !== currentCategory) return false;
        if (searchText) {{
            const q = searchText.toLowerCase();
            if (!j.company.toLowerCase().includes(q) && !j.role.toLowerCase().includes(q)) return false;
        }}
        return true;
    }});
}}

function render() {{
    const filtered = filterJobs();
    const open = filtered.filter(j => !j.is_closed);
    const closed = filtered.filter(j => j.is_closed);
    const sorted = [...open.sort((a,b) => (b.date_posted||'').localeCompare(a.date_posted||'')), ...closed];

    document.getElementById('stats').innerHTML = `
        <div class="stat"><div class="stat-number">${{filtered.length}}</div><div class="stat-label">Total</div></div>
        <div class="stat"><div class="stat-number">${{open.length}}</div><div class="stat-label">Open</div></div>
        <div class="stat"><div class="stat-number">${{closed.length}}</div><div class="stat-label">Closed</div></div>
    `;

    const tbody = document.getElementById('jobs-table');
    if (sorted.length === 0) {{
        tbody.innerHTML = '';
        document.getElementById('empty-state').style.display = 'block';
        return;
    }}
    document.getElementById('empty-state').style.display = 'none';

    tbody.innerHTML = sorted.map(j => {{
        const badge = j.experience_type === 'new_grad'
            ? '<span class="badge badge-ng">New Grad</span>'
            : `<span class="badge badge-el">${{j.min_years}}-${{j.max_years}} YOE</span>`;
        const apply = j.is_closed
            ? '<span class="closed">🔒 Closed</span>'
            : `<a href="${{j.url}}" target="_blank" class="apply-btn">Apply</a>`;
        return `<tr>
            <td class="company">${{j.company}}</td>
            <td class="role">${{j.role}}</td>
            <td class="location">${{j.location}}</td>
            <td>${{badge}}</td>
            <td class="age">${{ageDisplay(j.date_posted)}}</td>
            <td>${{apply}}</td>
        </tr>`;
    }}).join('');
}}

document.querySelectorAll('.tab').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTier = btn.dataset.tier;
        document.getElementById('yoe-group').style.display = currentTier === 'entry_level' ? '' : 'none';
        render();
    }});
}});

document.querySelectorAll('.yoe-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.yoe-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentYoe = btn.dataset.yoe;
        render();
    }});
}});

document.getElementById('category-filter').addEventListener('change', e => {{
    currentCategory = e.target.value;
    render();
}});

document.getElementById('search-input').addEventListener('input', e => {{
    searchText = e.target.value;
    render();
}});

populateCategories();
render();
</script>
</body>
</html>"""


def run():
    jobs = load_jobs()
    html = generate_html(jobs)
    with open(HTML_PATH, "w") as f:
        f.write(html)
    print(f"Generated jobs.html with {len(jobs)} job listings")


if __name__ == "__main__":
    run()
