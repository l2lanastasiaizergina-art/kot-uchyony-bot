from __future__ import annotations

import secrets
from dataclasses import dataclass

from ortho_game_bot.database.game_repository import GameRepository
from ortho_game_bot.database.models import (
    AnswerOutcome,
    ChoiceQuestion,
    RoundCompletion,
    RoundSnapshot,
)
from ortho_game_bot.database.repositories import ContentRepository

from .distractors import generate_choice_options
from .levels import level_for_grade


class ContentUnavailableError(RuntimeError):
    """В выбранном классе недостаточно активных слов для полного раунда."""


@dataclass(frozen=True, slots=True)
class ChoiceTurn:
    outcome: AnswerOutcome
    next_question: ChoiceQuestion | None
    snapshot: RoundSnapshot | None
    completion: RoundCompletion | None


class GameService:
    """Сценарий игрового раунда, не зависящий от Telegram API."""

    def __init__(
        self,
        content: ContentRepository,
        games: GameRepository,
        *,
        round_size: int = 10,
    ) -> None:
        if not 1 <= round_size <= 30:
            raise ValueError("Размер раунда должен быть от 1 до 30")
        self.content = content
        self.games = games
        self.round_size = round_size

    async def start_choice_round(self, *, user_id: int, grade: int) -> ChoiceQuestion:
        level = level_for_grade(grade)
        words = await self.content.sample_words(
            grade_min=level.min_grade,
            grade_max=level.max_grade,
            max_difficulty=level.max_difficulty,
            limit=self.round_size,
        )
        if len(words) < self.round_size:
            raise ContentUnavailableError(
                f"На уровне {level.code} найдено только {len(words)} слов из {self.round_size}"
            )
        questions = [
            (
                word,
                generate_choice_options(
                    word.answer,
                    word.orthograms,
                    seed=f"{word.external_id}:{secrets.token_hex(8)}",
                ),
            )
            for word in words
        ]
        return await self.games.create_choice_session(
            user_id=user_id,
            grade=grade,
            questions=questions,
        )

    async def answer_choice(
        self,
        *,
        session_id: str,
        user_id: int,
        position: int,
        option_index: int,
    ) -> ChoiceTurn:
        outcome = await self.games.answer_choice(
            session_id=session_id,
            user_id=user_id,
            position=position,
            option_index=option_index,
        )
        if not outcome.finished:
            next_question = await self.games.get_current_question(
                session_id=session_id,
                user_id=user_id,
            )
            if next_question is None:
                raise RuntimeError("Не удалось получить следующий вопрос")
            return ChoiceTurn(outcome, next_question, None, None)

        snapshot = await self.games.round_snapshot(session_id=session_id, user_id=user_id)
        completion = await self.games.complete_round(session_id=session_id, user_id=user_id)
        return ChoiceTurn(outcome, None, snapshot, completion)
