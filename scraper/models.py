"""Data models for job listings."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class Job:
    company: str
    role: str
    location: str
    url: str
    date_posted: str  # ISO format date string
    category: str  # e.g., "Investment Banking", "Consulting", "Sales & Trading", etc.
    source: str  # e.g., "greenhouse", "lever", "manual"
    is_closed: bool = False
    requires_visa_sponsorship: bool = True
    us_citizenship_required: bool = False
    company_url: Optional[str] = None
    tags: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def age_str(self):
        """Return human-readable age string like '0d', '3d', '2w', '1mo'."""
        try:
            posted = datetime.fromisoformat(self.date_posted)
            delta = datetime.now() - posted
            days = delta.days
            if days == 0:
                return "0d"
            elif days < 7:
                return f"{days}d"
            elif days < 30:
                weeks = days // 7
                return f"{weeks}w"
            else:
                months = days // 30
                return f"{months}mo"
        except (ValueError, TypeError):
            return "?"
