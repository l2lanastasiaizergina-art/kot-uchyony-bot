from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\s+")
_DASHES = str.maketrans({"–": "-", "—": "-", "‑": "-"})


def normalize_answer(value: str, *, fold_yo: bool = False) -> str:
    """Нормализует ответ, не удаляя значимые буквы и дефисы."""
    normalized = unicodedata.normalize("NFKC", value).translate(_DASHES)
    normalized = _SPACES.sub(" ", normalized.strip().lower())
    if fold_yo:
        normalized = normalized.replace("ё", "е")
    return normalized


def answers_equal(actual: str, expected: str, *, accept_e_for_yo: bool) -> bool:
    return normalize_answer(actual, fold_yo=accept_e_for_yo) == normalize_answer(
        expected, fold_yo=accept_e_for_yo
    )

