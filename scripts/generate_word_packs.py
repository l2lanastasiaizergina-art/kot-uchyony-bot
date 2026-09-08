"""Конвертирует утверждённые методические подборки в JSON-пакеты игры."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from build_dictation_guides import DATA, parse_markup  # noqa: E402


def orthogram_spans(raw: str) -> tuple[str, list[dict[str, object]]]:
    answer, marks = parse_markup(raw)
    spans: list[dict[str, object]] = []
    start: int | None = None
    for index, marked in enumerate([*marks, False]):
        if marked and start is None:
            start = index
        elif not marked and start is not None:
            spans.append({"start": start, "end": index, "text": answer[start:index]})
            start = None
    return answer, spans


def stable_id(grade: int, answer: str) -> str:
    digest = hashlib.sha1(f"{grade}:{answer.lower()}".encode()).hexdigest()[:12]
    return f"g{grade:02d}-{digest}"


def difficulty_for_grade(grade: int) -> int:
    if grade <= 2:
        return 1
    if grade <= 4:
        return 2
    if grade <= 7:
        return 3
    if grade <= 9:
        return 4
    return 5


def build_pack(grade: int, config: dict[str, object]) -> dict[str, object]:
    words: list[dict[str, object]] = []
    seen: set[str] = set()
    for group_name, rule_text, raw_words in config["groups"]:
        for raw in raw_words:
            answer, orthograms = orthogram_spans(raw)
            unique_key = answer.casefold().replace("ё", "е")
            if unique_key in seen:
                continue
            seen.add(unique_key)
            words.append(
                {
                    "id": stable_id(grade, answer),
                    "group": group_name,
                    "rule": rule_text,
                    "answer": answer,
                    "prompt": None,
                    "orthograms": orthograms,
                    "distractors": [],
                    "tags": [f"grade:{grade}", group_name],
                    "difficulty": difficulty_for_grade(grade),
                }
            )
    return {
        "schema_version": 1,
        "slug": f"grade-{grade:02d}-base",
        "version": 1,
        "grade": grade,
        "title": f"Орфографический минимум. {grade} класс",
        "description": config["focus"],
        "source": f"{grade:02d}_класс_Орфографические_словарные_диктанты.docx",
        "words": words,
    }


def main() -> None:
    output = PROJECT_ROOT / "data" / "words"
    output.mkdir(parents=True, exist_ok=True)
    total = 0
    for grade, config in sorted(DATA.items()):
        payload = build_pack(grade, config)
        destination = output / f"grade_{grade:02d}.json"
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        amount = len(payload["words"])
        total += amount
        print(f"{destination.name}: {amount}")
    print(f"Всего: {total}")


if __name__ == "__main__":
    main()

