"""Skill list hygiene: drop near-duplicates so skill lines read like a person wrote them."""

from __future__ import annotations

import re
from typing import Iterable, List


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", text.lower()).strip()


def _contains(longer: str, shorter: str) -> bool:
    """True if ``shorter`` appears in ``longer`` as whole words."""
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(shorter)}(?![a-z0-9])", longer))


def dedupe_skills(skills: Iterable[str], also_covered_by: Iterable[str] = ()) -> List[str]:
    """Remove repeated and subsumed skills while keeping the original order.

    A skill is dropped when its words are fully contained in a longer skill (or in one of
    ``also_covered_by``), e.g. 'Google Ads' and 'SEA' next to 'Google Ads (SEA)', or
    'Meta Ads' when the tools list already names 'Meta Ads Manager'.
    Exact duplicates (case-insensitive) keep only their first occurrence.
    """
    ordered = [s for s in skills if s and s.strip()]
    covering = [_key(s) for s in ordered] + [_key(c) for c in also_covered_by if c and c.strip()]

    kept: List[str] = []
    seen = set()
    for skill in ordered:
        k = _key(skill)
        if not k or k in seen:
            continue
        subsumed = any(len(other) > len(k) and _contains(other, k) for other in covering)
        covered_exactly = any(_key(c) == k for c in also_covered_by if c)
        if subsumed or covered_exactly:
            continue
        seen.add(k)
        kept.append(skill)
    return kept
