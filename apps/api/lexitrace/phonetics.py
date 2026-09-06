from __future__ import annotations

import re
import unicodedata

from rapidfuzz.fuzz import ratio

TRANSLITERATION_EQUIVALENTS = (
    ("ksh", "x"),
    ("ck", "k"),
    ("sh", "s"),
    ("th", "t"),
    ("dh", "d"),
    ("bh", "b"),
    ("ph", "f"),
    ("aa", "a"),
    ("ee", "i"),
    ("oo", "u"),
    ("ou", "u"),
    ("ai", "y"),
)


def transliteration_skeleton(value: str) -> str:
    """Normalize common Romanization choices without claiming language identification."""
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(character for character in normalized if character.isascii())
    normalized = re.sub(r"[^a-z]", "", normalized)
    for source, target in TRANSLITERATION_EQUIVALENTS:
        normalized = normalized.replace(source, target)
    return re.sub(r"(.)\1+", r"\1", normalized)


def indic_transliteration_similarity(left: str, right: str) -> float:
    """Return a graded similarity over a transparent Romanization skeleton."""
    left_skeleton = transliteration_skeleton(left)
    right_skeleton = transliteration_skeleton(right)
    if not left_skeleton or not right_skeleton:
        return 0.0
    return ratio(left_skeleton, right_skeleton) / 100
