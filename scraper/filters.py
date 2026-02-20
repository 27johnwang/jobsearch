"""Finance role filtering and classification logic."""

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
            r"trader\b",
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
            r"(?:research|investment)\s*analyst",
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
            r"financial\s*analyst",
            r"treasury\s*analyst",
        ],
    },
    "Risk Management": {
        "keywords": [
            r"risk\s*(?:manage|analyst|associate)", r"credit\s*risk",
            r"market\s*risk", r"operational\s*risk", r"enterprise\s*risk",
            r"compliance\b", r"regulatory\b", r"basel\b",
            r"stress\s*test", r"var\b", r"value\s*at\s*risk",
        ],
        "title_patterns": [
            r"risk\s*(?:analyst|associate|manage)",
            r"compliance\s*(?:analyst|associate)",
        ],
    },
    "Financial Technology": {
        "keywords": [
            r"fintech\b", r"financial\s*(?:tech|software|system|data)",
            r"payment", r"blockchain", r"(?:digital|crypto)\s*(?:asset|currenc)",
            r"banking\s*(?:tech|software|platform|engineer)",
        ],
        "title_patterns": [
            r"(?:fintech|financial\s*tech)",
            r"(?:software|data)\s*engineer.*(?:financ|bank|trad)",
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
            r"(?:sales|relationship)\s*(?:analyst|associate|manage)",
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
    # Exchanges / Market Infrastructure
    "nyse", "nasdaq", "cme group", "ice", "cboe",
    "dtcc", "bloomberg", "refinitiv", "s&p global",
    "moody's", "fitch", "msci", "morningstar",
    "ihs markit", "factset", "pitchbook",
    # Insurance / Other Financial
    "aig", "metlife", "prudential", "allstate",
    "berkshire hathaway", "liberty mutual", "travelers",
    "american express", "amex", "visa", "mastercard",
    "paypal", "discover", "capital one",
}

# New grad / entry level indicators
NEW_GRAD_PATTERNS = [
    r"new\s*grad", r"entry\s*level", r"junior\b", r"analyst\s*(?:1|i|program)",
    r"associate\s*(?:1|i|program)", r"rotational\s*(?:program|analyst)",
    r"graduate\s*(?:program|analyst|associate|role|position)",
    r"(?:20)?2[56]\s*(?:grad|new\s*hire|class|start)",
    r"campus\s*(?:hire|recruit|program)",
    r"early\s*career", r"university\s*(?:hire|recruit|grad)",
    r"(?:bachelor|bs|ba|undergraduate).*(?:require|prefer|degree)",
    r"0[\s-]*(?:2|3)\s*years?\s*(?:of\s*)?experience",
    r"(?:first|1st)\s*year\s*analyst",
]

# Exclusion patterns (roles that are NOT new grad)
EXCLUSION_PATTERNS = [
    r"senior\b", r"sr\.\b", r"lead\b", r"principal\b", r"director\b",
    r"head\s*of\b", r"manager\b(?!.*program)", r"vp\b", r"vice\s*president",
    r"(?:5|6|7|8|9|10)\+?\s*years", r"experienced\s*hire",
    r"intern\b(?!.*convert)", r"internship\b",
    r"mba\s*(?:require|prefer|hire|recruit)",
    r"phd\s*(?:require|prefer)",
]


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

    # If from a finance company but no specific category matched,
    # try to infer from the title
    if best_score == 0 and is_finance_company:
        title_lower = title.lower()
        if "product" in title_lower and "manage" in title_lower:
            return "Product Management (Finance)"
        if any(w in title_lower for w in ["sales", "business develop", "relationship"]):
            return "Sales (Financial Services)"
        if any(w in title_lower for w in ["analyst", "associate", "finance", "financial"]):
            return "Corporate Finance"
        # Generic finance company role
        return "Financial Technology"

    return best_category if best_score > 0 else None


def is_new_grad(title: str, description: str = "") -> bool:
    """Determine if a job listing is for new graduates / entry level."""
    text = f"{title} {description}".lower()

    # Check exclusion patterns first
    for pattern in EXCLUSION_PATTERNS:
        if re.search(pattern, text):
            return False

    # Check new grad patterns
    for pattern in NEW_GRAD_PATTERNS:
        if re.search(pattern, text):
            return True

    # Heuristic: if title contains "analyst" or "associate" without senior qualifiers
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["analyst", "associate i", "associate 1"]):
        if not any(kw in title_lower for kw in ["senior", "sr.", "lead", "principal"]):
            return True

    return False


def is_2026_role(title: str, description: str = "", date_posted: str = "") -> bool:
    """Check if this is a 2026 new grad role (or recent enough to be relevant)."""
    text = f"{title} {description}".lower()

    # Explicit 2026 mention
    if re.search(r"202[56]", text):
        return True

    # If posted in 2025-2026, likely relevant
    if date_posted:
        try:
            year = int(date_posted[:4])
            if year >= 2025:
                return True
        except (ValueError, IndexError):
            pass

    return True  # Default to including if uncertain
