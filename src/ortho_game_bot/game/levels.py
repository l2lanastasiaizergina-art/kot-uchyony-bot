from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrthographyLevel:
    code: str
    title: str
    anchor_grade: int
    min_grade: int
    max_grade: int
    max_difficulty: int | None = None


ORTHOGRAPHY_LEVELS = (
    OrthographyLevel("A0", "С нуля", 1, 1, 1, 1),
    OrthographyLevel("A1", "Начальный", 2, 1, 2),
    OrthographyLevel("A2", "Базовый", 4, 3, 4),
    OrthographyLevel("B1", "Уверенный", 7, 5, 7),
    OrthographyLevel("B2", "Продвинутый", 9, 8, 9),
    OrthographyLevel("C1", "Мастер", 11, 10, 11),
)


def level_for_grade(grade: int) -> OrthographyLevel:
    """Сопоставляет прежний номер класса новой универсальной ступени."""
    if not 1 <= grade <= 11:
        raise ValueError("Уровень должен соответствовать программе 1–11 классов")
    for level in ORTHOGRAPHY_LEVELS:
        if grade <= level.anchor_grade:
            return level
    return ORTHOGRAPHY_LEVELS[-1]
