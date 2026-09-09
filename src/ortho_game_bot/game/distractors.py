from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

VOWEL_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "а": ("о", "я"),
    "о": ("а",),
    "е": ("и", "ё", "э"),
    "ё": ("е", "о"),
    "и": ("е", "ы"),
    "ы": ("и",),
    "э": ("е",),
    "я": ("е", "а"),
    "ю": ("у",),
    "у": ("ю",),
}

FINAL_CONSONANT_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "б": ("п",), "п": ("б",), "в": ("ф",), "ф": ("в",),
    "г": ("к",), "к": ("г",), "д": ("т",), "т": ("д",),
    "ж": ("ш",), "ш": ("ж",), "з": ("с",), "с": ("з",),
}

COMMON_WORD_ERRORS: dict[str, tuple[str, str, str]] = {
    "берёза": ("бирёза", "береза", "биреза"),
    "воробей": ("варабей", "воробий", "варабий"),
    "корова": ("карова", "корава", "корово"),
    "молоко": ("малоко", "молако", "малако"),
    "морковь": ("марковь", "морков", "марков"),
    "огурец": ("агурец", "огуриц", "огурэц"),
    "собака": ("сабака", "собока", "сабока"),
    "ягода": ("ягада", "егода", "ягодо"),
}

LETTER_COMBINATIONS: tuple[tuple[str, str], ...] = (
    ("жи", "жы"), ("ши", "шы"), ("ча", "чя"), ("ща", "щя"),
    ("чу", "чю"), ("щу", "щю"), ("чк", "чьк"), ("чн", "чьн"),
    ("тся", "ться"), ("ться", "тся"),
)


def _with_case(replacement: str, original: str) -> str:
    return replacement.upper() if original.isupper() else replacement


def _replace_at(value: str, index: int, replacement: str) -> str:
    return value[:index] + _with_case(replacement, value[index]) + value[index + 1 :]


def _orthogram_indices(answer: str, orthograms: Iterable[dict[str, Any]]) -> list[int]:
    indices: list[int] = []
    for span in orthograms:
        start = int(span.get("start", 0))
        end = int(span.get("end", start))
        indices.extend(range(max(0, start), min(len(answer), end)))
    return list(dict.fromkeys(indices))


def _single_error_variants(value: str, preferred: Iterable[int] = ()) -> list[str]:
    variants: list[str] = []
    order = list(dict.fromkeys([*preferred, *range(len(value))]))
    for index in order:
        char = value[index].lower()
        for replacement in VOWEL_CONFUSIONS.get(char, ()):
            variants.append(_replace_at(value, index, replacement))
        if char in FINAL_CONSONANT_CONFUSIONS and (
            index == len(value) - 1 or not value[index + 1].lower() in VOWEL_CONFUSIONS
        ):
            for replacement in FINAL_CONSONANT_CONFUSIONS[char]:
                variants.append(_replace_at(value, index, replacement))
        if char in {"ь", "ъ"}:
            variants.append(value[:index] + value[index + 1 :])
            variants.append(_replace_at(value, index, "ъ" if char == "ь" else "ь"))

    lowered = value.lower()
    for correct, mistaken in LETTER_COMBINATIONS:
        start = 0
        while (index := lowered.find(correct, start)) >= 0:
            replacement = mistaken.upper() if value[index:index + len(correct)].isupper() else mistaken
            variants.append(value[:index] + replacement + value[index + len(correct):])
            start = index + 1

    if "-" in value:
        variants.extend((value.replace("-", ""), value.replace("-", " ")))
    if " " in value:
        variants.extend((value.replace(" ", ""), value.replace(" ", "-")))
    for index in range(1, len(value)):
        if value[index].isalpha() and value[index].lower() == value[index - 1].lower():
            variants.append(value[:index] + value[index + 1 :])
    return variants


def generate_choice_options(
    answer: str,
    orthograms: Iterable[dict[str, Any]],
    *,
    seed: str | int | None = None,
) -> tuple[str, str, str, str]:
    """Возвращает правильное слово и три варианта с типичными орфографическими ошибками."""
    rng = random.Random(seed)
    preferred = _orthogram_indices(answer, orthograms)
    candidates = [*COMMON_WORD_ERRORS.get(answer.casefold(), ())]
    candidates.extend(_single_error_variants(answer, preferred))

    # Для коротких слов допустимы варианты с двумя осмысленными ошибками.
    # Случайные перестановки, выпадение букв и бессмысленные наборы не создаются.
    for first_variant in tuple(candidates):
        if len(candidates) >= 18:
            break
        candidates.extend(_single_error_variants(first_variant))

    unique: list[str] = []
    seen = {answer.casefold()}
    for candidate in candidates:
        key = candidate.casefold()
        if key in seen or not candidate.strip():
            continue
        seen.add(key)
        unique.append(candidate)

    if len(unique) < 3:
        raise ValueError(f"Не удалось создать правдоподобные варианты для слова: {answer!r}")
    options = [answer, *unique[:3]]
    rng.shuffle(options)
    return tuple(options)  # type: ignore[return-value]
