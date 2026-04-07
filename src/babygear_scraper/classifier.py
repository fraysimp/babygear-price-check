"""Classify listings into categories and extract brand/model info."""

from __future__ import annotations

import re

from .config import CATEGORY_KEYWORDS, KNOWN_BRANDS
from .models import Category, Condition


def classify_category(title: str, description: str = "") -> Category:
    """Classify a listing into a baby gear category based on text matching."""
    text = f"{title} {description}".lower()
    scores: dict[Category, int] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[category] = score

    if not scores:
        return Category.OTHER
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def extract_brand(title: str, description: str = "") -> str | None:
    """Try to identify a known brand from the listing text."""
    text = f"{title} {description}"
    for brand in KNOWN_BRANDS:
        if re.search(re.escape(brand), text, re.IGNORECASE):
            return brand
    return None


def parse_condition(text: str) -> Condition:
    """Parse condition from listing text."""
    lower = text.lower()
    if any(w in lower for w in ["brand new", "bnib", "nib", "sealed", "unopened"]):
        return Condition.NEW
    if any(w in lower for w in ["like new", "excellent", "barely used", "mint"]):
        return Condition.LIKE_NEW
    if any(w in lower for w in ["good condition", "good shape", "gently used", "lightly used"]):
        return Condition.GOOD
    if any(w in lower for w in ["fair", "some wear", "used", "signs of wear"]):
        return Condition.FAIR
    if any(w in lower for w in ["poor", "damaged", "broken", "parts only"]):
        return Condition.POOR
    return Condition.UNKNOWN


def parse_price(text: str) -> int | None:
    """Extract price in cents from text like '$150' or '$25.50'."""
    match = re.search(r"\$\s*([\d,]+(?:\.\d{1,2})?)", text)
    if match:
        price_str = match.group(1).replace(",", "")
        return int(float(price_str) * 100)
    return None
