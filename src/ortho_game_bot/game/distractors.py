from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

VOWEL_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "а": ("о",),
    "о": ("а",),
    "е": ("и", "ё"),
    "ё": ("е", "о"),
    "и": ("е", "ы"),
    "ы": ("и",),
    "я": ("е", "а"),
    "ю": ("у",),
    "у": ("ю",),
}

CONSONANT_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "б": ("п",),
    "п": ("б",),
    "в": ("ф",),
    "ф": ("в",),
    "г": ("к",),
    "к": ("г",),
    "д": ("т",),
    "т": ("д",),
    "ж": ("ш",),
    "ш": ("ж",),
    "з": ("с",),
    "с": ("з",),
}


def _with_case(replacement: str, original: str) -> str:
    return replacement.upper() if original.isupper() else replacement


def _replace_at(value: str, index: int, replacement: str) -> str:
    return value[:index] + _with_case(replacement, value[index]) + value[index + 1 :]


def _letter_variants(value: str, indices: Iterable[int]) -> list[str]:
    variants: list[str] = []
    for index in indices:
        if not 0 <= index < len(value):
            continue
        char = value[index].lower()
        for replacement in VOWEL_CONFUSIONS.get(char, ()):
            variants.append(_replace_at(value, index, replacement))
        for replacement in CONSONANT_CONFUSIONS.get(char, ()):
            variants.append(_replace_at(value, index, replacement))
        if char in {"ь", "ъ"}:
            variants.append(value[:index] + value[index + 1 :])
            variants.append(_replace_at(value, index, "ъ" if char == "ь" else "ь"))
    return variants


def _structural_variants(value: str) -> list[str]:
    variants: list[str] = []
    if "-" in value:
        variants.extend((value.replace("-", ""), value.replace("-", " ")))
    if " " in value:
        variants.extend((value.replace(" ", ""), value.replace(" ", "-")))
    for index in range(1, len(value)):
        if value[index].isalpha() and value[index] == value[index - 1]:
            variants.append(value[:index] + value[index + 1 :])
        elif value[index].isalpha() and value[index - 1].isalpha():
            variants.append(value[:index] + value[index] + value[index:])
    return variants


def _orthogram_indices(answer: str, orthograms: Iterable[dict[str, Any]]) -> list[int]:
    indices: list[int] = []
    for span in orthograms:
        start = int(span.get("start", 0))
        end = int(span.get("end", start))
        indices.extend(range(max(0, start), min(len(answer), end)))
    return list(dict.fromkeys(indices))


def generate_choice_options(
    answer: str,
    orthograms: Iterable[dict[str, Any]],
    *,
    seed: str | int | None = None,
) -> tuple[str, str, str, str]:
    """Создаёт правильный ответ и три правдоподобных ошибочных написания."""
    rng = random.Random(seed)
    candidates: list[str] = []
    indices = _orthogram_indices(answer, orthograms)
    candidates.extend(_letter_variants(answer, indices))
    candidates.extend(_structural_variants(answer))
    candidates.extend(_letter_variants(answer, range(len(answer))))

    # Последний резерв для очень коротких слов или слов без размеченной орфограммы.
    for index, char in enumerate(answer):
        if not char.isalpha():
            continue
        candidates.append(answer[:index] + char + answer[index:])
        if len(answer) > 2:
            candidates.append(answer[:index] + answer[index + 1 :])

    unique: list[str] = []
    seen = {answer.casefold()}
    for candidate in candidates:
        key = candidate.casefold()
        if key in seen or not candidate.strip():
            continue
        seen.add(key)
        unique.append(candidate)

    if len(unique) < 3:
        raise ValueError(f"Не удалось создать варианты для слова: {answer!r}")
    rng.shuffle(unique)
    options = [answer, *unique[:3]]
    rng.shuffle(options)
    return tuple(options)  # type: ignore[return-value]

