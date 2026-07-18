"""Finance role filtering and classification logic.

STRICT filtering: only match actual new-grad analyst programs at finance
companies, not generic "Data Analyst" or "Account Executive" roles.
"""

import re
from typing import Optional

# Category definitions with keyword patterns
CATEGORIES = {
    "Investment Banking": {
        "keywords": [
            r"investment\s*bank", r"\bib\b", r"ibd\b", r"m&a\b", r"mergers",
            r"capital\s*markets", r"dcm\b", r"ecm\b", r"leveraged\s*finance",
            r"debt\s*capital", r"equity\s*capital", r"restructuring",
            r"coverage\s*analyst", r"deal\s*execution",
        ],
        "title_patterns": [
            r"investment\s*banking\s*analyst",
            r"ib\s*analyst",
            r"ibd\s*analyst",
        ],
    },
    "Sales & Trading": {
        "keywords": [
            r"sales\s*(?:and|&)\s*trading", r"s&t\b", r"trading\s*(?:analyst|associate)",
            r"fixed\s*income", r"equities\s*(?:trading|sales)", r"ficc\b",
            r"market\s*making", r"execution\s*trader", r"flow\s*trading",
            r"rates\s*trading", r"credit\s*trading", r"fx\s*trading",
            r"commodities\s*trading",
        ],
        "title_patterns": [
            r"(?:sales|trading)\s*analyst",
            r"sales\s*(?:and|&)\s*trading",
        ],
    },
    "Consulting": {
        "keywords": [
            r"management\s*consult", r"strategy\s*consult", r"business\s*consult",
            r"financial\s*(?:advisory|consult)", r"(?:transaction|deal)\s*advisory",
            r"valuation\s*(?:analyst|associate|consult)",
            r"due\s*diligence", r"fdd\b", r"forensic\s*account",
        ],
        "title_patterns": [
            r"(?:management|strategy|business|financial)\s*consult",
            r"(?:associate|analyst)\s*consult",
            r"advisory\s*(?:analyst|associate)",
        ],
    },
    "Asset Management": {
        "keywords": [
            r"asset\s*manage", r"portfolio\s*manage", r"investment\s*manage",
            r"wealth\s*manage", r"fund\s*manage", r"hedge\s*fund",
            r"mutual\s*fund", r"etf\b", r"private\s*equity",
            r"venture\s*capital", r"aum\b",
        ],
        "title_patterns": [
            r"(?:asset|portfolio|investment|wealth)\s*manage",
        ],
    },
    "Quantitative Finance": {
        "keywords": [
            r"quant(?:itative)?\s*(?:analyst|research|develop|trad|strat|finance)",
            r"algorithmic\s*trad", r"systematic\s*trad",
            r"financial\s*engineer", r"risk\s*model",
            r"derivatives?\s*(?:pricing|model)", r"strats\b",
        ],
        "title_patterns": [
            r"quant\b", r"quantitative",
            r"financial\s*engineer",
            r"strats?\s*(?:analyst|associate)",
        ],
    },
    "Corporate Finance": {
        "keywords": [
            r"corporate\s*finance", r"fp&a\b", r"financial\s*plan",
            r"treasury\b", r"corporate\s*develop", r"investor\s*relations",
            r"financial\s*report", r"sec\s*report", r"sox\b",
            r"internal\s*audit", r"financial\s*control",
        ],
        "title_patterns": [
            r"fp&a\s*analyst",
            r"(?:corporate\s*)?finance\s*(?:analyst|associate|rotational)",
            r"treasury\s*analyst",
        ],
    },
    "Risk Management": {
        "keywords": [
            r"risk\s*(?:manage|analyst|associate)", r"credit\s*risk",
            r"market\s*risk", r"operational\s*risk", r"enterprise\s*risk",
            r"stress\s*test", r"var\b", r"value\s*at\s*risk",
        ],
        "title_patterns": [
            r"risk\s*(?:analyst|associate|manage)",
            r"compliance\s*(?:analyst|associate)",
        ],
    },
    "Financial Technology": {
        "keywords": [
            r"fintech\b",
            r"blockchain", r"(?:digital|crypto)\s*(?:asset|currenc)",
        ],
        "title_patterns": [
            r"(?:fintech|financial\s*tech)",
        ],
    },
    "Product Management (Finance)": {
        "keywords": [
            r"product\s*manage.*(?:financ|bank|trad|invest|payment)",
            r"(?:financ|bank|trad|invest|payment).*product\s*manage",
        ],
        "title_patterns": [
            r"product\s*manage",
        ],
    },
    "Sales (Financial Services)": {
        "keywords": [
            r"(?:institutional|financial)\s*sales",
            r"sales.*(?:financ|bank|invest|securi)",
            r"relationship\s*manage.*(?:financ|bank|invest)",
            r"client\s*(?:service|manage).*(?:financ|bank|invest)",
            r"business\s*develop.*(?:financ|bank|invest)",
        ],
        "title_patterns": [
            r"(?:institutional|financial)\s*sales",
        ],
    },
}

# Companies known to be in finance / have large finance divisions
FINANCE_COMPANIES = {
    # Investment Banks
    "goldman sachs", "morgan stanley", "jp morgan", "jpmorgan", "j.p. morgan",
    "bank of america", "bofa", "citigroup", "citi", "barclays",
    "deutsche bank", "ubs", "credit suisse", "hsbc", "wells fargo",
    "jefferies", "lazard", "evercore", "moelis", "centerview",
    "pjt partners", "perella weinberg", "houlihan lokey", "guggenheim",
    "greenhill", "rothschild", "nomura", "mizuho", "rbc capital",
    "td securities", "bmo capital", "scotiabank",
    # Consulting
    "mckinsey", "bain", "bcg", "boston consulting", "deloitte",
    "pwc", "pricewaterhousecoopers", "ey", "ernst & young", "kpmg",
    "oliver wyman", "a.t. kearney", "roland berger", "l.e.k.",
    "simon-kucher", "alvarez & marsal",
    # Asset Management / PE / VC
    "blackrock", "vanguard", "fidelity", "state street", "pimco",
    "bridgewater", "citadel", "two sigma", "de shaw", "d.e. shaw",
    "point72", "millennium", "ares management", "apollo",
    "blackstone", "kkr", "carlyle", "tpg", "warburg pincus",
    "general atlantic", "advent international", "bain capital",
    "silver lake", "thoma bravo", "vista equity",
    "sequoia", "andreessen horowitz", "a16z", "benchmark",
    "wellington management", "t. rowe price", "invesco",
    "franklin templeton", "capital group",
    # FinTech
    "stripe", "square", "block", "plaid", "robinhood",
    "coinbase", "sofi", "affirm", "chime", "brex",
    "marqeta", "wise", "revolut", "nubank", "klarna",
    "adyen", "checkout.com", "ripple", "circle",
    "ramp", "rho", "wealthsimple", "acorns", "betterment",
    "figure", "mercury", "upstart",
    # Exchanges / Market Infrastructure
    "nyse", "nasdaq", "cme group", "ice", "cboe",
    "dtcc", "bloomberg", "refinitiv", "s&p global",
    "moody's", "fitch", "msci", "morningstar",
    "ihs markit", "factset", "pitchbook",
    # Quant / Trading
    "jane street", "imc", "jump trading", "old mission",
    "marshall wace", "man group", "flow traders",
    "akuna capital", "transmarket", "squarepoint",
    "schonfeld", "aqr", "worldquant",
    # Insurance / Other Financial
    "aig", "metlife", "prudential", "allstate",
    "berkshire hathaway", "liberty mutual", "travelers",
    "american express", "amex", "visa", "mastercard",
    "paypal", "discover", "capital one",
    "northern trust", "ally financial",
    "bloomberg", "koch industries",
    "t. rowe price", "vanguard", "fidelity",
}

# ------------------------------------------------------------------
# STRICT title-level signals that a role is a new-grad program
# ------------------------------------------------------------------

# These must appear in the TITLE (not just the description body) for
# a role to be considered new-grad.  The old heuristic "any title with
# 'analyst' from a finance company" was far too broad.
_NEW_GRAD_TITLE_PATTERNS = [
    r"new\s*grad",
    r"new\s*college\s*grad",
    r"(?:202[5-8])\s*(?:analyst|associate|graduate|trader|researcher)",
    r"(?:analyst|associate|graduate|trader|researcher)\s*(?:program|programme)",
    r"(?:analyst|associate|trader|researcher)\s*[-–—]?\s*(?:202[5-8])",
    r"(?:rotational|rotation)\s*(?:program|analyst|associate)",
    r"(?:analyst|associate)\s*development\s*program",
    r"campus\s*(?:analyst|associate|hire|recruit|program)",
    r"early\s*career",
    r"university\s*grad",
    r"graduate\s*(?:program|programme|trainee|training|analyst|associate|trader|researcher)",
    r"entry[\s-]*level\s*(?:analyst|associate|consultant|trader)",
    r"(?:full[\s-]*time)\s*(?:analyst|associate)\s*(?:202[5-8])",
    r"(?:class\s*of|cohort)\s*202[5-8]",
]

_NEW_GRAD_TITLE_RE = re.compile(
    "|".join(_NEW_GRAD_TITLE_PATTERNS), re.IGNORECASE
)

# Body-level signals (lower confidence — only used to confirm, not as sole signal)
_NEW_GRAD_BODY_PATTERNS = [
    r"new\s*grad", r"recent\s*grad",
    r"0[\s-]*(?:1|2|3)\s*years?\s*(?:of\s*)?experience",
    r"(?:bachelor|bs|ba|undergraduate).*(?:require|prefer|degree)",
    r"campus\s*(?:hire|recruit|program)",
    r"class\s*of\s*202[5-8]",
]

_NEW_GRAD_BODY_RE = re.compile(
    "|".join(_NEW_GRAD_BODY_PATTERNS), re.IGNORECASE
)

# Exclusion patterns (roles that are NOT new grad)
EXCLUSION_PATTERNS = [
    r"senior\b", r"sr\.\b", r"lead\b", r"principal\b", r"director\b",
    r"head\s*of\b", r"manager\b(?!.*program)", r"vp\b", r"vice\s*president",
    r"(?:3|4|5|6|7|8|9|10)\+?\s*years", r"experienced\s*hire",
    r"intern\b(?!.*convert)", r"internship\b",
    r"summer\s*analyst", r"summer\s*associate",
    r"mba\s*(?:require|prefer|hire|recruit)",
    r"phd\s*(?:require|prefer)",
    r"staff\s*(?:engineer|analyst)",
    r"ii\b", r"iii\b", r"level\s*[3-9]",
    r"apprentice\b", r"learnership\b",
]

_EXCLUSION_RE = re.compile("|".join(EXCLUSION_PATTERNS), re.IGNORECASE)


def classify_role(title: str, description: str = "", company: str = "") -> Optional[str]:
    """Classify a job into a finance category. Returns None if not finance-related."""
    text = f"{title} {description}".lower()
    company_lower = company.lower()

    # Check if it's from a known finance company
    is_finance_company = any(fc in company_lower for fc in FINANCE_COMPANIES)

    # Try to match against category patterns
    best_category = None
    best_score = 0

    for category, patterns in CATEGORIES.items():
        score = 0

        # Check title patterns (higher weight)
        for pattern in patterns.get("title_patterns", []):
            if re.search(pattern, title.lower()):
                score += 3

        # Check keyword patterns
        for pattern in patterns.get("keywords", []):
            if re.search(pattern, text):
                score += 1

        if score > best_score:
            best_score = score
            best_category = category

    # For finance companies with no specific category match, only classify
    # if title strongly suggests a finance new-grad program role
    if best_score == 0 and is_finance_company:
        title_lower = title.lower()
        # Only accept titles that look like actual programs, not generic roles
        if re.search(r"(?:new\s*grad|program|rotational|202[5-8])", title_lower):
            if "product" in title_lower and "manage" in title_lower:
                return "Product Management (Finance)"
            if any(w in title_lower for w in ["sales", "business develop", "relationship"]):
                return "Sales (Financial Services)"
            return "Corporate Finance"
        # Don't auto-classify generic titles like "Data Analyst", "Software Engineer"
        return None

    return best_category if best_score > 0 else None


_ENTRY_LEVEL_TITLE_PATTERNS = [
    r"entry[\s-]*level",
    r"junior\b",
    r"(?:0|1|2)[\s-]*(?:to|\-)[\s-]*(?:1|2|3)\s*(?:year|yr)",
    r"analyst\s+[i1]\b(?!\s*(?:i|[2-9]))",
    r"associate\s+[i1]\b(?!\s*(?:i|[2-9]))",
]

_ENTRY_LEVEL_TITLE_RE = re.compile(
    "|".join(_ENTRY_LEVEL_TITLE_PATTERNS), re.IGNORECASE
)

_CAMPUS_PROGRAM_RE = re.compile(
    r"(?:202[6-9])\s*(?:analyst|associate|graduate|trader|researcher)|"
    r"(?:analyst|associate|graduate|trader|researcher)\s*(?:program|programme)|"
    r"(?:rotational|rotation)\s*(?:program|analyst|associate)|"
    r"(?:analyst|associate)\s*development\s*program|"
    r"campus\s*(?:analyst|associate|hire|recruit|program)|"
    r"new\s*grad|new\s*college\s*grad|university\s*grad|"
    r"graduate\s*(?:program|programme|trainee|training)|"
    r"(?:class\s*of|cohort)\s*202[6-9]|"
    r"(?:full[\s-]*time)\s*(?:analyst|associate)\s*(?:202[6-9])",
    re.IGNORECASE,
)

_YOE_PATTERN = re.compile(
    r"(\d+)\s*[\-\+to]*\s*(\d*)\s*(?:year|yr)s?\s*(?:of\s*)?(?:experience|exp)",
    re.IGNORECASE,
)


def classify_experience(title: str, description: str = "") -> tuple:
    """Classify a job as new_grad or entry_level and return (type, min_years, max_years).

    Returns:
        ("new_grad", 0, 0) for campus recruiting / 2027 programs
        ("entry_level", min, max) for entry-level roles with 0-2 YOE
    """
    text = f"{title} {description}"

    if _CAMPUS_PROGRAM_RE.search(title):
        return ("new_grad", 0, 0)

    m = _YOE_PATTERN.search(text)
    if m:
        min_y = int(m.group(1))
        max_y = int(m.group(2)) if m.group(2) else min_y
        if max_y <= 2:
            return ("entry_level", min_y, max_y)
        if min_y <= 2:
            return ("entry_level", min_y, min(max_y, 2))

    if _ENTRY_LEVEL_TITLE_RE.search(title):
        return ("entry_level", 0, 2)

    if _CAMPUS_PROGRAM_RE.search(description):
        return ("new_grad", 0, 0)

    return ("new_grad", 0, 0)


def is_new_grad(title: str, description: str = "") -> bool:
    """Determine if a job listing is for new graduates / entry level.

    STRICT: the title itself must contain a new-grad signal. We no longer
    accept bare "analyst" titles — that matched thousands of mid-career roles.
    """
    # Check exclusion patterns first (on full text)
    text = f"{title} {description}"
    if _EXCLUSION_RE.search(text):
        return False

    # Strong signal: title explicitly says new grad / program / 2026
    if _NEW_GRAD_TITLE_RE.search(title):
        return True

    # Moderate signal: title has "analyst" or "associate" AND body confirms new-grad
    title_lower = title.lower()
    has_junior_title = any(kw in title_lower for kw in [
        "analyst", "associate i", "associate 1", "junior",
    ])
    if has_junior_title and description and _NEW_GRAD_BODY_RE.search(description):
        return True

    return False


def is_entry_level_role(title: str, description: str = "") -> bool:
    """Determine if a job is an entry-level analyst role (0-2 YOE).

    Broader than is_new_grad — accepts roles that say "entry level",
    "junior", "analyst I", or have 0-2 years experience mentioned.
    """
    text = f"{title} {description}"
    if _EXCLUSION_RE.search(text):
        return False

    if _NEW_GRAD_TITLE_RE.search(title):
        return True

    if _ENTRY_LEVEL_TITLE_RE.search(title):
        return True

    title_lower = title.lower()
    has_junior_title = any(kw in title_lower for kw in [
        "analyst", "associate i", "associate 1", "junior",
    ])
    if has_junior_title and description and _NEW_GRAD_BODY_RE.search(description):
        return True

    m = _YOE_PATTERN.search(text)
    if m:
        min_y = int(m.group(1))
        if min_y <= 2:
            return True

    return False


def is_2026_role(title: str, description: str = "", date_posted: str = "") -> bool:
    """Check if this is a 2026 new grad role (or recent enough to be relevant)."""
    text = f"{title} {description}".lower()

    # Explicit 2025/2026/2027 mention
    if re.search(r"202[5-8]", text):
        return True

    # If posted in 2025+, likely relevant
    if date_posted:
        try:
            year = int(date_posted[:4])
            if year >= 2025:
                return True
        except (ValueError, IndexError):
            pass

    # Without any signal, default to EXCLUDING (not including)
    return False
