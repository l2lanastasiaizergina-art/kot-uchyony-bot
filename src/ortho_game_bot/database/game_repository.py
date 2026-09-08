from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ortho_game_bot.game.retention import calculate_daily_reward, league_for_score
from ortho_game_bot.game.scoring import calculate_answer_score
from ortho_game_bot.utils.text import normalize_answer
from ortho_game_bot.utils.time import period_key

from .connection import Database
from .models import (
    AnswerOutcome,
    ChoiceQuestion,
    GameWord,
    RoundCompletion,
    RoundSnapshot,
)


class GameError(RuntimeError):
    """Базовая ошибка игрового раунда."""


class GameNotFoundError(GameError):
    pass


class StaleAnswerError(GameError):
    pass


class InvalidOptionError(GameError):
    pass


class GameRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_choice_session(
        self,
        *,
        user_id: int,
        grade: int,
        questions: list[tuple[GameWord, tuple[str, str, str, str]]],
    ) -> ChoiceQuestion:
        if not questions:
            raise ValueError("Раунд не может быть пустым")
        session_id = uuid.uuid4().hex

        def operation(connection: sqlite3.Connection) -> None:
            if connection.execute(
                "SELECT 1 FROM users WHERE telegram_id = ?", (user_id,)
            ).fetchone() is None:
                raise LookupError("Пользователь не найден")
            connection.execute(
                """
                UPDATE game_sessions
                SET status = 'abandoned', finished_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND status = 'active'
                """,
                (user_id,),
            )
            connection.execute(
                """
                INSERT INTO game_sessions(id, user_id, mode, grade, questions_total)
                VALUES (?, ?, 'choice', ?, ?)
                """,
                (session_id, user_id, grade, len(questions)),
            )
            connection.executemany(
                """
                INSERT INTO game_session_questions(session_id, position, word_id, options_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (session_id, position, word.id, json.dumps(options, ensure_ascii=False))
                    for position, (word, options) in enumerate(questions)
                ],
            )

        await self.database.write(operation)
        question = await self.get_current_question(session_id=session_id, user_id=user_id)
        assert question is not None
        return question

    async def get_current_question(
        self, *, session_id: str, user_id: int
    ) -> ChoiceQuestion | None:
        row = await self.database.read_one(
            """
            SELECT s.id AS session_id, s.current_index, s.questions_total,
                   q.word_id, q.options_json, w.group_name, w.rule_text
            FROM game_sessions s
            JOIN game_session_questions q
              ON q.session_id = s.id AND q.position = s.current_index
            JOIN words w ON w.id = q.word_id
            WHERE s.id = ? AND s.user_id = ? AND s.status = 'active'
            """,
            (session_id, user_id),
        )
        if row is None:
            return None
        return ChoiceQuestion(
            session_id=row["session_id"],
            position=row["current_index"],
            total=row["questions_total"],
            word_id=row["word_id"],
            options=tuple(json.loads(row["options_json"])),
            group_name=row["group_name"],
            rule_text=row["rule_text"],
        )

    async def answer_choice(
        self,
        *,
        session_id: str,
        user_id: int,
        position: int,
        option_index: int,
    ) -> AnswerOutcome:
        current_period = period_key()

        def operation(connection: sqlite3.Connection) -> AnswerOutcome:
            row = connection.execute(
                """
                SELECT s.status, s.current_index, s.questions_total, s.current_streak,
                       s.score_delta, s.correct_count, s.wrong_count,
                       q.word_id, q.options_json, w.word
                FROM game_sessions s
                JOIN game_session_questions q
                  ON q.session_id = s.id AND q.position = ?
                JOIN words w ON w.id = q.word_id
                WHERE s.id = ? AND s.user_id = ?
                """,
                (position, session_id, user_id),
            ).fetchone()
            if row is None:
                raise GameNotFoundError("Раунд не найден")
            if row["status"] != "active" or row["current_index"] != position:
                raise StaleAnswerError("Этот ответ уже принят")

            options = tuple(json.loads(row["options_json"]))
            if not 0 <= option_index < len(options):
                raise InvalidOptionError("Некорректный вариант ответа")
            selected = options[option_index]
            correct_answer = row["word"]
            is_correct = normalize_answer(selected) == normalize_answer(correct_answer)
            score = calculate_answer_score(
                is_correct=is_correct, streak_before=row["current_streak"]
            )
            next_index = position + 1
            finished = next_index >= row["questions_total"]
            score_so_far = row["score_delta"] + score.points
            correct_count = row["correct_count"] + int(is_correct)
            wrong_count = row["wrong_count"] + int(not is_correct)

            connection.execute(
                """
                INSERT INTO game_answers(
                    session_id, word_id, question_index, prompt_snapshot,
                    correct_answer_snapshot, user_answer, is_correct, points_awarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    row["word_id"],
                    position,
                    "Выберите верное написание",
                    correct_answer,
                    selected,
                    int(is_correct),
                    score.points,
                ),
            )
            connection.execute(
                """
                UPDATE game_sessions SET
                    current_index = ?, score_delta = ?, correct_count = ?, wrong_count = ?,
                    current_streak = ?, best_streak = MAX(best_streak, ?),
                    status = ?, finished_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE id = ?
                """,
                (
                    next_index,
                    score_so_far,
                    correct_count,
                    wrong_count,
                    score.streak_after,
                    score.streak_after,
                    "finished" if finished else "active",
                    int(finished),
                    session_id,
                ),
            )
            self._apply_answer_score(
                connection=connection,
                user_id=user_id,
                session_id=session_id,
                position=position,
                points=score.points,
                is_correct=is_correct,
                streak_after=score.streak_after,
                current_period=current_period,
            )
            self._update_review_queue(
                connection=connection,
                user_id=user_id,
                word_id=row["word_id"],
                is_correct=is_correct,
            )
            return AnswerOutcome(
                session_id=session_id,
                position=position,
                total=row["questions_total"],
                selected_answer=selected,
                correct_answer=correct_answer,
                is_correct=is_correct,
                points=score.points,
                streak_after=score.streak_after,
                score_so_far=score_so_far,
                correct_count=correct_count,
                wrong_count=wrong_count,
                finished=finished,
            )

        return await self.database.write(operation)

    @staticmethod
    def _apply_answer_score(
        *,
        connection: sqlite3.Connection,
        user_id: int,
        session_id: str,
        position: int,
        points: int,
        is_correct: bool,
        streak_after: int,
        current_period: str,
    ) -> None:
        user = connection.execute(
            "SELECT total_score FROM users WHERE telegram_id = ?", (user_id,)
        ).fetchone()
        if user is None:
            raise LookupError("Пользователь не найден")
        monthly = connection.execute(
            "SELECT score FROM monthly_scores WHERE user_id = ? AND period_key = ?",
            (user_id, current_period),
        ).fetchone()
        old_monthly = monthly["score"] if monthly else 0
        new_total = max(0, user["total_score"] + points)
        new_monthly = max(0, old_monthly + points)
        effective_total = new_total - user["total_score"]
        effective_monthly = new_monthly - old_monthly
        idempotency_key = f"{session_id}:answer:{position}"
        connection.execute(
            """
            INSERT INTO score_events(
                id, user_id, source_type, source_id, delta_total, delta_monthly,
                period_key, idempotency_key, metadata_json
            ) VALUES (?, ?, 'game_answer', ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                user_id,
                session_id,
                effective_total,
                effective_monthly,
                current_period,
                idempotency_key,
                json.dumps({"position": position, "correct": is_correct}),
            ),
        )
        connection.execute(
            """
            INSERT INTO monthly_scores(
                user_id, period_key, score, correct_answers, wrong_answers
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, period_key) DO UPDATE SET
                score = excluded.score,
                correct_answers = monthly_scores.correct_answers + excluded.correct_answers,
                wrong_answers = monthly_scores.wrong_answers + excluded.wrong_answers,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, current_period, new_monthly, int(is_correct), int(not is_correct)),
        )
        connection.execute(
            """
            UPDATE users SET
                total_score = ?, monthly_score = ?, monthly_period = ?,
                correct_answers = correct_answers + ?,
                wrong_answers = wrong_answers + ?,
                current_streak = ?, best_streak = MAX(best_streak, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (
                new_total,
                new_monthly,
                current_period,
                int(is_correct),
                int(not is_correct),
                streak_after,
                streak_after,
                user_id,
            ),
        )

    @staticmethod
    def _update_review_queue(
        *,
        connection: sqlite3.Connection,
        user_id: int,
        word_id: int,
        is_correct: bool,
    ) -> None:
        existing = connection.execute(
            "SELECT repetitions, lapses FROM review_queue WHERE user_id = ? AND word_id = ?",
            (user_id, word_id),
        ).fetchone()
        now = datetime.now(timezone.utc)
        if not is_correct:
            next_review = (now + timedelta(days=1)).isoformat()
            connection.execute(
                """
                INSERT INTO review_queue(
                    user_id, word_id, status, repetitions, lapses,
                    interval_days, next_review_at, last_answer_correct
                ) VALUES (?, ?, 'learning', 0, 1, 1, ?, 0)
                ON CONFLICT(user_id, word_id) DO UPDATE SET
                    status = 'learning', repetitions = 0,
                    lapses = review_queue.lapses + 1, interval_days = 1,
                    next_review_at = excluded.next_review_at,
                    last_answer_correct = 0, updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, word_id, next_review),
            )
            return

        # Правильно отвеченные новые слова не попадают в очередь ошибок.
        if existing is None:
            return
        repetitions = existing["repetitions"] + 1
        intervals = (1, 3, 7, 14)
        interval = intervals[min(repetitions, len(intervals) - 1)]
        status = "mastered" if repetitions >= 3 else "review"
        connection.execute(
            """
            UPDATE review_queue SET
                status = ?, repetitions = ?, interval_days = ?,
                next_review_at = ?, last_answer_correct = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND word_id = ?
            """,
            (
                status,
                repetitions,
                interval,
                (now + timedelta(days=interval)).isoformat(),
                user_id,
                word_id,
            ),
        )

    async def round_snapshot(self, *, session_id: str, user_id: int) -> RoundSnapshot:
        row = await self.database.read_one(
            """
            SELECT id, user_id, questions_total, score_delta, correct_count,
                   wrong_count, best_streak, completion_applied
            FROM game_sessions
            WHERE id = ? AND user_id = ? AND status = 'finished'
            """,
            (session_id, user_id),
        )
        if row is None:
            raise GameNotFoundError("Завершённый раунд не найден")
        return RoundSnapshot(
            session_id=row["id"],
            user_id=row["user_id"],
            questions_total=row["questions_total"],
            raw_score=row["score_delta"],
            correct_count=row["correct_count"],
            wrong_count=row["wrong_count"],
            best_streak=row["best_streak"],
            completion_applied=bool(row["completion_applied"]),
        )

    async def complete_round(self, *, session_id: str, user_id: int) -> RoundCompletion:
        current_period = period_key()

        def operation(connection: sqlite3.Connection) -> RoundCompletion:
            session = connection.execute(
                """
                SELECT questions_total, score_delta, correct_count, wrong_count,
                       completion_applied
                FROM game_sessions
                WHERE id = ? AND user_id = ? AND status = 'finished'
                """,
                (session_id, user_id),
            ).fetchone()
            user = connection.execute(
                """
                SELECT total_score, daily_streak, longest_daily_streak,
                       last_qualifying_date, timezone_name
                FROM users WHERE telegram_id = ?
                """,
                (user_id,),
            ).fetchone()
            if session is None or user is None:
                raise GameNotFoundError("Завершённый раунд не найден")

            today = self._local_date(user["timezone_name"])
            activity = connection.execute(
                "SELECT * FROM daily_activity WHERE user_id = ? AND activity_date = ?",
                (user_id, today.isoformat()),
            ).fetchone()
            current_monthly = connection.execute(
                "SELECT score FROM monthly_scores WHERE user_id = ? AND period_key = ?",
                (user_id, current_period),
            ).fetchone()
            monthly_score = current_monthly["score"] if current_monthly else 0

            if session["completion_applied"]:
                return RoundCompletion(
                    applied=False,
                    daily_streak=user["daily_streak"],
                    multiplier_percent=100,
                    bonus_points=0,
                    awarded_points=session["score_delta"],
                    total_score=user["total_score"],
                    monthly_score=monthly_score,
                    league_title=league_for_score(user["total_score"]).title,
                )

            previous_qualified = bool(activity and activity["streak_qualified"])
            new_streak = user["daily_streak"]
            qualifies = session["questions_total"] >= 10
            if qualifies and not previous_qualified:
                new_streak = self._next_daily_streak(
                    previous=user["last_qualifying_date"], today=today, current=new_streak
                )

            boosted_used = activity["boosted_rounds"] if activity else 0
            reward = calculate_daily_reward(
                raw_points=session["score_delta"],
                streak_days=new_streak,
                boosted_rounds_used=boosted_used,
            )
            bonus = reward.bonus_points
            new_total = user["total_score"] + bonus
            new_monthly = monthly_score + bonus
            event_key = f"{session_id}:complete"
            connection.execute(
                """
                INSERT INTO score_events(
                    id, user_id, source_type, source_id, delta_total, delta_monthly,
                    period_key, idempotency_key, metadata_json
                ) VALUES (?, ?, 'round_bonus', ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    user_id,
                    session_id,
                    bonus,
                    bonus,
                    current_period,
                    event_key,
                    json.dumps(
                        {
                            "daily_streak": new_streak,
                            "multiplier_percent": reward.multiplier_percent,
                        }
                    ),
                ),
            )
            connection.execute(
                """
                INSERT INTO monthly_scores(user_id, period_key, score, games_played)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, period_key) DO UPDATE SET
                    score = excluded.score,
                    games_played = monthly_scores.games_played + 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, current_period, new_monthly),
            )
            connection.execute(
                """
                UPDATE users SET
                    total_score = ?, monthly_score = ?, monthly_period = ?,
                    games_played = games_played + 1,
                    daily_streak = ?, longest_daily_streak = MAX(longest_daily_streak, ?),
                    last_qualifying_date = CASE WHEN ? THEN ? ELSE last_qualifying_date END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
                """,
                (
                    new_total,
                    new_monthly,
                    current_period,
                    new_streak,
                    new_streak,
                    int(qualifies),
                    today.isoformat(),
                    user_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO daily_activity(
                    user_id, activity_date, answers_attempted, correct_answers,
                    raw_points, bonus_points, boosted_rounds, streak_qualified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, activity_date) DO UPDATE SET
                    answers_attempted =
                        daily_activity.answers_attempted + excluded.answers_attempted,
                    correct_answers = daily_activity.correct_answers + excluded.correct_answers,
                    raw_points = daily_activity.raw_points + excluded.raw_points,
                    bonus_points = daily_activity.bonus_points + excluded.bonus_points,
                    boosted_rounds = daily_activity.boosted_rounds + excluded.boosted_rounds,
                    streak_qualified = MAX(
                        daily_activity.streak_qualified, excluded.streak_qualified
                    ),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    today.isoformat(),
                    session["questions_total"],
                    session["correct_count"],
                    session["score_delta"],
                    bonus,
                    int(session["score_delta"] > 0 and boosted_used < 3),
                    int(qualifies),
                ),
            )
            connection.execute(
                "UPDATE game_sessions SET completion_applied = 1 WHERE id = ?",
                (session_id,),
            )
            return RoundCompletion(
                applied=True,
                daily_streak=new_streak,
                multiplier_percent=reward.multiplier_percent,
                bonus_points=bonus,
                awarded_points=reward.awarded_points,
                total_score=new_total,
                monthly_score=new_monthly,
                league_title=league_for_score(new_total).title,
            )

        return await self.database.write(operation)

    @staticmethod
    def _local_date(timezone_name: str) -> date:
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            zone = timezone.utc
        return datetime.now(zone).date()

    @staticmethod
    def _next_daily_streak(*, previous: str | None, today: date, current: int) -> int:
        if previous == today.isoformat():
            return max(1, current)
        if previous == (today - timedelta(days=1)).isoformat():
            return max(0, current) + 1
        return 1
