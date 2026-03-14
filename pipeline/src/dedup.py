"""Simple deduplication module for Milan apartment finder."""

import hashlib
import re
from difflib import SequenceMatcher


# Common Italian address abbreviation mappings (canonical -> variants)
_ABBREVIATIONS: list[tuple[str, list[str]]] = [
    ("via", ["v.", "v"]),
    ("viale", ["v.le", "vle"]),
    ("piazza", ["p.za", "p.zza", "pza", "pzza"]),
    ("piazzale", ["p.le", "ple"]),
    ("corso", ["c.so", "cso"]),
    ("largo", ["l.go", "lgo"]),
    ("vicolo", ["vic."]),
    ("strada", ["str."]),
]


def normalize_address(address: str) -> str:
    """Normalize an address string for consistent comparison.

    Lowercases, strips whitespace, and expands common Italian
    address abbreviations to their canonical forms.
    """
    if not address:
        return ""

    text = address.lower().strip()
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Replace abbreviations with canonical forms
    for canonical, variants in _ABBREVIATIONS:
        for abbr in variants:
            # Word-boundary-aware replacement
            pattern = re.compile(r"\b" + re.escape(abbr) + r"\b", re.IGNORECASE)
            text = pattern.sub(canonical, text)

    return text.strip()


def generate_listing_id(address: str, price: int, size_sqm: int) -> str:
    """Generate a stable hash ID from normalized address + price + size.

    Returns the first 12 hex characters of the MD5 hash.
    """
    norm = normalize_address(address)
    raw = f"{norm}|{price}|{size_sqm}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def is_likely_duplicate(listing1: dict, listing2: dict) -> bool:
    """Fuzzy duplicate check between two listings.

    Returns True if:
    - Normalized addresses are > 80% similar, AND
    - Prices are within 50 EUR of each other, AND
    - Sizes are within 5 sqm of each other.
    """
    addr1 = normalize_address(listing1.get("address", ""))
    addr2 = normalize_address(listing2.get("address", ""))

    # Address similarity
    similarity = SequenceMatcher(None, addr1, addr2).ratio()
    if similarity <= 0.80:
        return False

    # Price proximity
    price1 = listing1.get("price", 0) or 0
    price2 = listing2.get("price", 0) or 0
    if abs(price1 - price2) > 50:
        return False

    # Size proximity
    size1 = listing1.get("size_sqm", 0) or 0
    size2 = listing2.get("size_sqm", 0) or 0
    if abs(size1 - size2) > 5:
        return False

    return True
