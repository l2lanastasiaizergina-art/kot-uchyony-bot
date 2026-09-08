from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ortho_game_bot.config import Settings
from ortho_game_bot.database import UserRepository
from ortho_game_bot.game.retention import daily_multiplier_percent
from ortho_game_bot.keyboards import (
    grade_keyboard,
    leaderboard_keyboard,
    main_menu_keyboard,
)

router = Router(name="common")


async def _profile_text(telegram_id: int, users: UserRepository) -> str:
    user = await users.get(telegram_id)
    if not user:
        return "Сначала нажмите /start."
    accuracy_total = user.correct_answers + user.wrong_answers
    accuracy = round(user.correct_answers / accuracy_total * 100) if accuracy_total else 0
    grade = f"{user.grade} класс" if user.grade else "не выбран"
    multiplier = daily_multiplier_percent(user.daily_streak) / 100
    return (
        "<b>👤 Мой профиль</b>\n\n"
        f"Класс: <b>{grade}</b>\n"
        f"Всего очков: <b>{user.total_score}</b>\n"
        f"За месяц: <b>{user.monthly_score}</b>\n"
        f"Игр сыграно: <b>{user.games_played}</b>\n"
        f"Точность: <b>{accuracy}%</b>\n"
        f"Лучшая серия ответов: <b>{user.best_streak}</b> 🔥\n"
        f"Дней подряд: <b>{user.daily_streak}</b> ⚡\n"
        f"Множитель сегодня: <b>×{multiplier:g}</b>"
    )


@router.message(CommandStart())
async def start(message: Message, users: UserRepository, settings: Settings) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await users.register_or_update(
        telegram_id=tg_user.id,
        username=tg_user.username,
        display_name=tg_user.full_name,
    )
    if user.grade is None:
        await message.answer(
            "<b>Привет! Я Кот Учёный 🐈‍⬛📚</b>\n\nВыбери свой класс:",
            reply_markup=grade_keyboard(),
        )
        return
    await message.answer(
        f"С возвращением! Твой уровень — <b>{user.grade} класс</b>.",
        reply_markup=main_menu_keyboard(settings.webapp_url),
    )


@router.callback_query(F.data == "grade:change")
async def change_grade(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("Выбери свой класс:", reply_markup=grade_keyboard())


@router.callback_query(F.data.startswith("grade:"))
async def set_grade(callback: CallbackQuery, users: UserRepository, settings: Settings) -> None:
    await callback.answer()
    if callback.data == "grade:change" or callback.from_user is None:
        return
    try:
        grade = int(callback.data.split(":", maxsplit=1)[1])
        await users.set_grade(callback.from_user.id, grade)
    except (ValueError, LookupError):
        await callback.answer("Не удалось выбрать класс", show_alert=True)
        return
    if callback.message:
        await callback.message.edit_text(
            f"Отлично! Выбран <b>{grade} класс</b>. Можно начинать тренировку.",
            reply_markup=main_menu_keyboard(settings.webapp_url),
        )


@router.message(Command("profile"))
async def profile_command(message: Message, users: UserRepository, settings: Settings) -> None:
    if message.from_user:
        await message.answer(
            await _profile_text(message.from_user.id, users),
            reply_markup=main_menu_keyboard(settings.webapp_url),
        )


@router.callback_query(F.data == "profile")
async def profile_callback(
    callback: CallbackQuery, users: UserRepository, settings: Settings
) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            await _profile_text(callback.from_user.id, users),
            reply_markup=main_menu_keyboard(settings.webapp_url),
        )


@router.message(Command("leaderboard"))
async def leaderboard_command(message: Message, users: UserRepository) -> None:
    rows = await users.leaderboard(limit=10)
    text = "<b>🏆 Общий рейтинг</b>\n\n" + "\n".join(
        f"{row.position}. {escape(row.display_name)} — <b>{row.score}</b>" for row in rows
    )
    await message.answer(
        text if rows else "Рейтинг пока пуст.",
        reply_markup=leaderboard_keyboard(),
    )


@router.callback_query(F.data.startswith("leaderboard:"))
async def leaderboard_callback(callback: CallbackQuery, users: UserRepository) -> None:
    scope_name = callback.data.rsplit(":", maxsplit=1)[-1] if callback.data else "global"
    user = await users.get(callback.from_user.id)
    grade = user.grade if user and scope_name == "class" else None
    if scope_name == "class" and grade is None:
        await callback.answer("Сначала выбери класс", show_alert=True)
        return
    scope = "monthly" if scope_name == "monthly" else "global"
    rows = await users.leaderboard(scope=scope, grade=grade, limit=10)
    title = {
        "global": "🏆 Общий рейтинг",
        "class": f"📚 Рейтинг: {grade} класс",
        "monthly": "📅 Рейтинг за месяц",
    }.get(scope_name, "🏆 Общий рейтинг")
    body = "\n".join(
        f"{row.position}. {escape(row.display_name)} — <b>{row.score}</b>" for row in rows
    )
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            f"<b>{title}</b>\n\n" + (body or "Рейтинг пока пуст."),
            reply_markup=leaderboard_keyboard(),
        )


@router.callback_query(F.data == "menu:main")
async def main_menu(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            "<b>🐈‍⬛ Кот Учёный</b>\n\nДокажи, что ты самый грамотный!",
            reply_markup=main_menu_keyboard(settings.webapp_url),
        )
