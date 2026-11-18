"""Keyword emergency guardrail (§6.7). Checks raw user text for emergency
language before anything else happens: no AI call, no proposal. This is the
first of two layers; an LLM-based check is still to do (Kunj).
"""

import re

from app.views import messages

# Add or remove phrases here; everything else adapts. Entries are regex
# fragments (not escaped), so plurals/misspellings use "s?"/"e?" and word
# boundaries are added automatically around each one -- keep entries
# lowercase and use the apostrophe form only ("can't"/"it's"/"won't"), since
# any phrase containing "can't" automatically also matches
# "cant"/"cannot"/"can not" (people rarely type the apostrophe).
#
# "fell", "stroke", and "bleeding" are deliberately narrow: on their own they
# block a lot of ordinary messages ("I fell asleep", "my stroke doctor", "my
# gums are bleeding a little"), and for an older adult with a history of
# falls, strokes, or a bleeding condition, any message mentioning it would
# never reach the AI or the care team (see plan.md §6.7).
EMERGENCY_PHRASES = [
    "chest pains?",
    "can't breathe?",  # also matches "breath" (common misspelling)
    "trouble breathing",
    "hard to breathe",
    "i fell(?!\\s+asleep)",  # not "fell asleep"
    "fell down",
    "had a fall",
    "having a stroke",
    "think it's a stroke",
    "heart attack",
    "bleeding a lot",
    "heavy bleeding",
    "won't stop bleeding",
    "bleeding badly",
    "suicide",
]

_CANT_VARIANTS = ["can't", "cant", "cannot", "can not"]


def _expand_cant_variants(phrase: str) -> list[str]:
    if "can't" not in phrase:
        return [phrase]
    return [phrase.replace("can't", variant) for variant in _CANT_VARIANTS]


_WHITESPACE_RE = re.compile(r"\s+")
_ALL_PHRASES = [
    variant for phrase in EMERGENCY_PHRASES for variant in _expand_cant_variants(phrase)
]
_PHRASE_PATTERNS = [re.compile(rf"\b{phrase}\b") for phrase in _ALL_PHRASES]


def _normalize(text: str) -> str:
    """Lowercase, straighten curly apostrophes, and collapse repeated spaces."""
    text = text.replace("’", "'")
    return _WHITESPACE_RE.sub(" ", text.lower()).strip()


def check_emergency(text: str) -> str | None:
    """Return the emergency message if `text` contains emergency language, else None."""
    normalized = _normalize(text)
    for pattern in _PHRASE_PATTERNS:
        if pattern.search(normalized):
            return messages.EMERGENCY_DETECTED
    return None
