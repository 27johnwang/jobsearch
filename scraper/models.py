"""Data models for job listings."""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional
import json


@dataclass
class Job:
    company: str
    role: str
    location: str
    url: str
    date_posted: str  # ISO date when ATS says it was posted (real date from API)
    category: str  # e.g., "Investment Banking", "Consulting", "Sales & Trading", etc.
    source: str  # e.g., "greenhouse", "lever", "manual"
    is_closed: bool = False
    requires_visa_sponsorship: bool = True
    us_citizenship_required: bool = False
    company_url: Optional[str] = None
    tags: list = field(default_factory=list)
    date_added: str = ""  # ISO date when we first discovered/added this listing

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def effective_date(self) -> str:
        """Best available date: prefer real ATS date, fall back to date_added."""
        return self.date_posted or self.date_added or ""

    @property
    def age_str(self) -> str:
        """Return human-readable age like '0d', '3d', '2w', '1mo'.

        Uses the real ATS posting date when available, otherwise the date
        we added it to the tracker.
        """
        d = self.effective_date
        if not d:
            return "?"
        try:
            posted = datetime.fromisoformat(d)
            delta = datetime.now() - posted
            days = delta.days
            if days < 0:
                return "0d"
            if days == 0:
                return "0d"
            if days < 7:
                return f"{days}d"
            if days < 30:
                weeks = days // 7
                return f"{weeks}w"
            months = days // 30
            return f"{months}mo"
        except (ValueError, TypeError):
            return "?"
