from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ortho_game_bot.database import (
    GameNotFoundError,
    InvalidOptionError,
    StaleAnswerError,
    UserRepository,
)
from ortho_game_bot.database.models import ChoiceQuestion
from ortho_game_bot.game.service import ContentUnavailableError, GameService
from ortho_game_bot.game.states import GameStates
from ortho_game_bot.keyboards.callbacks import ChoiceAnswer
from ortho_game_bot.keyboards.game import (
    choice_keyboard,
    game_mode_keyboard,
    round_end_keyboard,
)

router = Router(name="game")


def _progress(position: int, total: int) -> str:
    completed = min(total, position + 1)
    return "🟩" * completed + "⬜" * max(0, total - completed)


def _question_text(question: ChoiceQuestion) -> str:
    return (
        f"<b>Задание {question.position + 1} из {question.total}</b>\n"
        f"{_progress(question.position, question.total)}\n\n"
        "В каком варианте нет ошибки?"
    )


@router.callback_query(F.data == "game:menu")
async def game_menu(
    callback: CallbackQuery,
    users: UserRepository,
    state: FSMContext,
) -> None:
    await callback.answer()
    user = await users.get(callback.from_user.id)
    if user is None:
        if isinstance(callback.message, Message):
            await callback.message.answer("Сначала запусти бота командой /start.")
        return
    if user.grade is None:
        if isinstance(callback.message, Message):
            await callback.message.answer("Сначала выбери класс в профиле.")
        return
    await state.set_state(GameStates.choosing_mode)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "<b>🐈‍⬛ Тренировка Кота Учёного</b>\n\n"
            f"Уровень: <b>{user.grade} класс</b>. За правильный ответ — 10 очков, "
            "за ошибку — −2. Серии дают бонусы.",
            reply_markup=game_mode_keyboard(),
        )


@router.callback_query(F.data == "game:dictation:soon")
async def dictation_soon(callback: CallbackQuery) -> None:
    await callback.answer(
        "Добавим после подключения аудио: слово нельзя показывать до ответа.",
        show_alert=True,
    )


@router.callback_query(F.data == "game:start:choice")
async def start_choice_round(
    callback: CallbackQuery,
    users: UserRepository,
    game_service: GameService,
    state: FSMContext,
) -> None:
    user = await users.get(callback.from_user.id)
    if user is None or user.grade is None:
        await callback.answer("Сначала выбери класс через /start", show_alert=True)
        return
    try:
        question = await game_service.start_choice_round(
            user_id=callback.from_user.id,
            grade=user.grade,
        )
    except ContentUnavailableError:
        await callback.answer("Для этого класса пока недостаточно слов", show_alert=True)
        return
    await callback.answer()
    await state.set_state(GameStates.answering_choice)
    await state.update_data(session_id=question.session_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _question_text(question),
            reply_markup=choice_keyboard(question),
        )


@router.callback_query(ChoiceAnswer.filter())
async def answer_choice(
    callback: CallbackQuery,
    callback_data: ChoiceAnswer,
    game_service: GameService,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    stored_session = state_data.get("session_id")
    if stored_session is not None and stored_session != callback_data.session_id:
        await callback.answer("Это задание уже не активно", show_alert=True)
        return
    try:
        turn = await game_service.answer_choice(
            session_id=callback_data.session_id,
            user_id=callback.from_user.id,
            position=callback_data.position,
            option_index=callback_data.option,
        )
    except StaleAnswerError:
        await callback.answer("Ответ уже принят")
        return
    except (GameNotFoundError, InvalidOptionError):
        await callback.answer("Раунд больше не активен", show_alert=True)
        await state.clear()
        return

    await callback.answer("Верно!" if turn.outcome.is_correct else "Есть ошибка")
    if turn.next_question is not None:
        # Восстанавливает FSM после рестарта процесса: источник истины — SQLite.
        await state.set_state(GameStates.answering_choice)
        await state.update_data(session_id=callback_data.session_id)
    if not isinstance(callback.message, Message):
        return

    sign = "+" if turn.outcome.points >= 0 else ""
    if turn.outcome.is_correct:
        feedback = (
            f"✅ <b>{escape(turn.outcome.correct_answer)}</b>\n"
            f"{sign}{turn.outcome.points} очков"
        )
    else:
        feedback = (
            f"❌ Ты выбрал(а): <s>{escape(turn.outcome.selected_answer)}</s>\n"
            f"Правильно: <b>{escape(turn.outcome.correct_answer)}</b>\n"
            f"{sign}{turn.outcome.points} очка"
        )
    await callback.message.edit_text(feedback)

    if turn.next_question is not None:
        await callback.message.answer(
            _question_text(turn.next_question),
            reply_markup=choice_keyboard(turn.next_question),
        )
        return

    await state.clear()
    if turn.snapshot is None or turn.completion is None:
        await callback.message.answer("Раунд завершён, но статистика временно недоступна.")
        return
    accuracy = round(turn.snapshot.correct_count / turn.snapshot.questions_total * 100)
    multiplier = turn.completion.multiplier_percent / 100
    bonus_line = (
        f"\nБонус регулярности ×{multiplier:g}: "
        f"<b>+{turn.completion.bonus_points}</b>"
        if turn.completion.bonus_points > 0
        else ""
    )
    await callback.message.answer(
        "<b>🏁 Раунд завершён!</b>\n\n"
        f"Верно: <b>{turn.snapshot.correct_count}/{turn.snapshot.questions_total}</b>\n"
        f"Точность: <b>{accuracy}%</b>\n"
        f"Лучшая серия: <b>{turn.snapshot.best_streak}</b> 🔥\n"
        f"За раунд: <b>{turn.snapshot.raw_score}</b>{bonus_line}\n"
        f"Всего: <b>{turn.completion.total_score}</b>\n"
        f"Дней подряд: <b>{turn.completion.daily_streak}</b> ⚡\n"
        f"Лига: <b>{escape(turn.completion.league_title)}</b>",
        reply_markup=round_end_keyboard(),
    )
