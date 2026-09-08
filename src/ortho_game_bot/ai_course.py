from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ortho_game_bot.database.connection import Database


class AICourseError(RuntimeError):
    """Base error for the interactive AI literacy course."""


class AICourseNotFoundError(AICourseError):
    pass


class AICourseInvalidOptionError(AICourseError):
    pass


class AICourseStaleAnswerError(AICourseError):
    pass


@dataclass(frozen=True, slots=True)
class MissionCheckResult:
    mission_id: str
    attempt_number: int
    is_correct: bool
    allow_retry: bool
    check_completed: bool
    first_attempt_correct: bool


class AICourseContent:
    """Loads authored diagnostics and age-adapted missions without leaking answers."""

    DIAGNOSTIC_COUNT = 16
    MISSION_COUNT = 20

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if self.path.suffix == ".gz":
            with gzip.open(self.path, "rt", encoding="utf-8") as source:
                payload = json.load(source)
        else:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.product = str(payload.get("product", "Кот Учёный: Код ИИ"))
        self.subtitle = str(payload.get("subtitle", "20 миссий про ИИ"))
        self.age_profiles = tuple(payload.get("age_profiles", ()))
        self.competencies = tuple(payload.get("competencies", ()))
        self.worlds = tuple(payload.get("worlds", ()))
        self.track_variants = payload.get("track_variants", {})
        self._age_codes = {str(item["code"]) for item in self.age_profiles}
        self._diagnostic = payload.get("diagnostic", {})
        self._missions = {str(item["id"]): item for item in payload.get("missions", ())}
        self._validate()

    def _validate(self) -> None:
        if len(self._age_codes) != 4:
            raise ValueError("Для курса требуются четыре возрастных режима")
        if len(self.competencies) != 8:
            raise ValueError("Карта курса должна содержать восемь компетенций")
        competency_ids = {str(item["id"]) for item in self.competencies}
        for age_code in self._age_codes:
            tasks = self._diagnostic.get(age_code)
            if not isinstance(tasks, list) or len(tasks) != self.DIAGNOSTIC_COUNT:
                raise ValueError(f"Диагностика {age_code}: требуется 16 заданий")
            if len({str(task["task_id"]) for task in tasks}) != self.DIAGNOSTIC_COUNT:
                raise ValueError(f"Диагностика {age_code}: task_id должны быть уникальны")
            for task in tasks:
                if task.get("competency_id") not in competency_ids:
                    raise ValueError(f"Диагностика {age_code}: неизвестная компетенция")
                options = task.get("options")
                if not isinstance(options, list) or len(options) != 4:
                    raise ValueError(f"Диагностика {age_code}: требуется четыре ответа")
                if any(option.get("score") not in {0, 1, 2, 3} for option in options):
                    raise ValueError(f"Диагностика {age_code}: оценка должна быть 0–3")
        if len(self._missions) != self.MISSION_COUNT:
            raise ValueError("MVP курса должен содержать 20 миссий")
        for mission in self._missions.values():
            if mission.get("primary_competency") not in competency_ids:
                raise ValueError(f"Миссия {mission['id']}: неизвестная компетенция")
            variants = mission.get("variants", {})
            if set(variants) != self._age_codes:
                raise ValueError(f"Миссия {mission['id']}: нет всех возрастных версий")
            for variant in variants.values():
                check = variant.get("check", {})
                if len(check.get("options", ())) != 4:
                    raise ValueError(f"Миссия {mission['id']}: требуется четыре ответа")
                if check.get("correct_option") not in range(4):
                    raise ValueError(f"Миссия {mission['id']}: неверный correct_option")

    def validate_age_code(self, age_code: str) -> str:
        if age_code not in self._age_codes:
            raise AICourseError("Выберите один из четырёх возрастных режимов")
        return age_code

    def validate_track_code(self, age_code: str, track_code: str | None) -> str | None:
        if track_code is None:
            return None
        if track_code not in self.track_variants.get(age_code, {}):
            raise AICourseError("Выберите трек: учёба, работа или творчество")
        return track_code

    def mission_ids(self) -> tuple[str, ...]:
        return tuple(self._missions)

    def mission(self, mission_id: str) -> dict[str, Any]:
        try:
            return self._missions[mission_id]
        except KeyError as exc:
            raise AICourseNotFoundError("Миссия не найдена") from exc

    def mission_variant(self, mission_id: str, age_code: str) -> dict[str, Any]:
        self.validate_age_code(age_code)
        return self.mission(mission_id)["variants"][age_code]

    def diagnostic_task(self, age_code: str, task_id: str) -> dict[str, Any]:
        self.validate_age_code(age_code)
        for task in self._diagnostic[age_code]:
            if task["task_id"] == task_id:
                return task
        raise AICourseNotFoundError("Задание диагностики не найдено")

    def diagnostic_tasks(self, age_code: str) -> tuple[dict[str, Any], ...]:
        self.validate_age_code(age_code)
        return tuple(self._diagnostic[age_code])

    @staticmethod
    def public_diagnostic_task(task: dict[str, Any], position: int) -> dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "position": position,
            "total": AICourseContent.DIAGNOSTIC_COUNT,
            "competency_id": task["competency_id"],
            "facet": task["facet"],
            "question": task["question"],
            "options": [option["text"] for option in task["options"]],
        }

    @staticmethod
    def public_mission(mission: dict[str, Any], age_code: str) -> dict[str, Any]:
        variant = mission["variants"][age_code]
        check = variant["check"]
        return {
            "id": mission["id"],
            "world_id": mission["world_id"],
            "order": mission["order"],
            "title": variant["title"],
            "goal": mission["goal"],
            "primary_competency": mission["primary_competency"],
            "minutes": mission["minutes"],
            "xp": mission["xp"],
            "story_hook": variant["story_hook"],
            "theory": variant["theory"],
            "rule": variant["rule"],
            "check": {
                "prompt": check["prompt"],
                "options": check["options"],
            },
            "practical_task": variant["practical_task"],
            "evidence_prompt": variant["evidence_prompt"],
        }

    def diagnostic_score(self, age_code: str, task_id: str, option: int) -> int:
        if not 0 <= option < 4:
            raise AICourseInvalidOptionError("Выберите один из четырёх вариантов")
        return int(self.diagnostic_task(age_code, task_id)["options"][option]["score"])

    def mission_check(
        self, mission_id: str, age_code: str, option: int
    ) -> tuple[dict[str, Any], bool]:
        if not 0 <= option < 4:
            raise AICourseInvalidOptionError("Выберите один из четырёх вариантов")
        check = self.mission_variant(mission_id, age_code)["check"]
        return check, option == int(check["correct_option"])

    def diagnostic_summary(self, answers: list[dict[str, Any]]) -> dict[str, Any]:
        by_competency: dict[str, list[int]] = {str(item["id"]): [] for item in self.competencies}
        for answer in answers:
            by_competency[str(answer["competency_id"])].append(int(answer["score"]))
        results = []
        for competency in self.competencies:
            competency_id = str(competency["id"])
            values = by_competency[competency_id]
            percent = round(sum(values) / (len(values) * 3) * 100) if values else 0
            status = "Уверенно" if percent >= 70 else "Развиваем" if percent >= 40 else "Начинаем"
            results.append({
                "id": competency_id,
                "title": competency["title"],
                "percent": percent,
                "status": status,
            })
        weakest = min(results, key=lambda item: item["percent"])
        competency = next(
            item for item in self.competencies if item["id"] == weakest["id"]
        )
        world = next(
            (
                item
                for item in self.worlds
                if item["title"] == competency["world"]
            ),
            self.worlds[-1],
        )
        recommended = next(
            mission["id"]
            for mission in self._missions.values()
            if mission["world_id"] == world["id"]
        )
        overall = round(sum(item["percent"] for item in results) / len(results))
        return {
            "overall_percent": overall,
            "competencies": results,
            "weakest_competency": weakest["id"],
            "recommended_mission_id": recommended,
        }


class AICourseRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def profile(self, *, user_id: int) -> dict[str, Any] | None:
        row = await self.database.read_one(
            """
            SELECT user_id, age_code, track_code, created_at, updated_at
            FROM ai_course_profiles WHERE user_id = ?
            """,
            (user_id,),
        )
        return dict(row) if row else None

    async def set_profile(
        self, *, user_id: int, age_code: str, track_code: str | None = None
    ) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> None:
            if connection.execute(
                "SELECT 1 FROM users WHERE telegram_id = ?", (user_id,)
            ).fetchone() is None:
                raise LookupError("Пользователь не найден")
            connection.execute(
                """
                INSERT INTO ai_course_profiles(user_id, age_code, track_code)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    age_code = excluded.age_code,
                    track_code = COALESCE(excluded.track_code, ai_course_profiles.track_code),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, age_code, track_code),
            )

        await self.database.write(operation)
        profile = await self.profile(user_id=user_id)
        assert profile is not None
        return profile

    async def diagnostic_answers(self, *, user_id: int, age_code: str) -> list[dict[str, Any]]:
        rows = await self.database.read_all(
            """
            SELECT task_id, competency_id, selected_option, score, answered_at
            FROM ai_diagnostic_answers
            WHERE user_id = ? AND age_code = ?
            ORDER BY answered_at, task_id
            """,
            (user_id, age_code),
        )
        return [dict(row) for row in rows]

    async def answer_diagnostic(
        self,
        *,
        user_id: int,
        age_code: str,
        task_id: str,
        competency_id: str,
        selected_option: int,
        score: int,
    ) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            try:
                connection.execute(
                    """
                    INSERT INTO ai_diagnostic_answers(
                        user_id, age_code, task_id, competency_id, selected_option, score
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, age_code, task_id, competency_id, selected_option, score),
                )
            except sqlite3.IntegrityError as exc:
                raise AICourseStaleAnswerError("Этот ответ уже сохранён") from exc

        await self.database.write(operation)

    async def mission_progress(self, *, user_id: int, mission_id: str) -> dict[str, Any] | None:
        row = await self.database.read_one(
            """
            SELECT user_id, mission_id, status, attempts_count, check_completed,
                   first_attempt_correct, evidence_text, started_at, updated_at, completed_at
            FROM ai_mission_progress
            WHERE user_id = ? AND mission_id = ?
            """,
            (user_id, mission_id),
        )
        return dict(row) if row else None

    async def all_mission_progress(self, *, user_id: int) -> dict[str, dict[str, Any]]:
        rows = await self.database.read_all(
            """
            SELECT user_id, mission_id, status, attempts_count, check_completed,
                   first_attempt_correct, evidence_text, started_at, updated_at, completed_at
            FROM ai_mission_progress
            WHERE user_id = ? ORDER BY mission_id
            """,
            (user_id,),
        )
        return {str(row["mission_id"]): dict(row) for row in rows}

    async def start_mission(self, *, user_id: int, mission_id: str) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO ai_mission_progress(user_id, mission_id)
                VALUES (?, ?)
                ON CONFLICT(user_id, mission_id) DO NOTHING
                """,
                (user_id, mission_id),
            )

        await self.database.write(operation)
        progress = await self.mission_progress(user_id=user_id, mission_id=mission_id)
        assert progress is not None
        return progress

    async def answer_mission_check(
        self,
        *,
        user_id: int,
        mission_id: str,
        selected_option: int,
        correct_option: int,
    ) -> MissionCheckResult:
        def operation(connection: sqlite3.Connection) -> MissionCheckResult:
            progress = connection.execute(
                """
                SELECT status, attempts_count, check_completed
                FROM ai_mission_progress WHERE user_id = ? AND mission_id = ?
                """,
                (user_id, mission_id),
            ).fetchone()
            if progress is None:
                raise AICourseStaleAnswerError("Сначала откройте миссию")
            if progress["status"] == "completed" or progress["check_completed"]:
                raise AICourseStaleAnswerError("Проверка этой миссии уже завершена")
            attempt = int(progress["attempts_count"]) + 1
            if attempt > 2:
                raise AICourseStaleAnswerError("Попытки для этой проверки завершены")
            is_correct = selected_option == correct_option
            check_completed = is_correct or attempt == 2
            connection.execute(
                """
                INSERT INTO ai_mission_answers(
                    user_id, mission_id, attempt_number, selected_option, is_correct
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, mission_id, attempt, selected_option, int(is_correct)),
            )
            connection.execute(
                """
                UPDATE ai_mission_progress SET
                    attempts_count = ?,
                    check_completed = ?,
                    first_attempt_correct = CASE WHEN ? THEN 1 ELSE first_attempt_correct END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND mission_id = ?
                """,
                (
                    attempt,
                    int(check_completed),
                    int(is_correct and attempt == 1),
                    user_id,
                    mission_id,
                ),
            )
            return MissionCheckResult(
                mission_id=mission_id,
                attempt_number=attempt,
                is_correct=is_correct,
                allow_retry=not check_completed,
                check_completed=check_completed,
                first_attempt_correct=is_correct and attempt == 1,
            )

        return await self.database.write(operation)

    async def save_evidence(
        self, *, user_id: int, mission_id: str, evidence_text: str
    ) -> dict[str, Any]:
        evidence = " ".join(evidence_text.split())
        if not 8 <= len(evidence) <= 1200:
            raise AICourseError("Опишите результат практики: от 8 до 1200 символов")

        def operation(connection: sqlite3.Connection) -> bool:
            progress = connection.execute(
                """
                SELECT status, check_completed FROM ai_mission_progress
                WHERE user_id = ? AND mission_id = ?
                """,
                (user_id, mission_id),
            ).fetchone()
            if progress is None or not progress["check_completed"]:
                raise AICourseStaleAnswerError("Сначала завершите проверочный вопрос")
            if progress["status"] == "completed":
                raise AICourseStaleAnswerError("Эта миссия уже завершена")
            connection.execute(
                """
                UPDATE ai_mission_progress SET
                    status = 'completed', evidence_text = ?,
                    updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND mission_id = ?
                """,
                (evidence, user_id, mission_id),
            )
            return True

        await self.database.write(operation)
        progress = await self.mission_progress(user_id=user_id, mission_id=mission_id)
        assert progress is not None
        return progress
