"""Detect wording that makes a resume read as machine-written.

Shared by the validator (warnings) and the LLM system prompts (so the model is told
exactly which phrases to avoid). All checks are advisory: they never block a resume.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List

# Matched at a word start, so "spearhead" also catches "spearheaded".
BANNED_PHRASES: List[str] = [
    "results-driven",
    "result-driven",
    "passionate",
    "dynamic",
    "motivated",
    "proven track record",
    "track record of",
    "hands-on expertise",
    "leverage",
    "spearhead",
    "synergy",
    "cutting-edge",
    "seamless",
    "robust",
    "innovative",
    "drive measurable",
    "scalable",
    "thrive",
    "fast-paced",
    "team player",
    "detail-oriented",
    "self-starter",
    "go-getter",
    "highly skilled",
    "extensive experience",
    "strong interest",
    "excited to apply",
    "i am writing to express",
    "furthermore",
    "moreover",
    "in today's",
    "game-changer",
    "best-in-class",
    "unlock",
    "elevate",
    "holistic",
    "delve",
]

_BANNED_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(p) for p in BANNED_PHRASES) + r")", re.IGNORECASE)


def find_ai_tells(text: str) -> List[str]:
    """Return the distinct buzzwords / stock phrases found in ``text`` (lowercase, in order)."""
    seen: List[str] = []
    for match in _BANNED_RE.finditer(text or ""):
        phrase = match.group(1).lower()
        if phrase not in seen:
            seen.append(phrase)
    return seen


def repeated_openers(bullets: Iterable[str], limit: int = 3) -> List[str]:
    """First words that open ``limit`` or more of the given bullets (e.g. 'Executed' x3)."""
    openers = [b.split()[0].strip(",.:;").lower() for b in bullets if b and b.split()]
    return [word for word, count in Counter(openers).items() if count >= limit]


def dash_count(text: str) -> int:
    """Number of em/en dashes used as sentence punctuation (a common machine-writing tell)."""
    return len(re.findall(r"\s[—–]\s|—", text or ""))
