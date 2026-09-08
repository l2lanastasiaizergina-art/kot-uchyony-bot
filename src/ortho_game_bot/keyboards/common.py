from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def grade_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for grade in range(1, 12):
        builder.button(text=f"{grade} класс", callback_data=f"grade:{grade}")
    builder.adjust(3, 3, 3, 2)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", callback_data="game:menu")],
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard:global"),
            ],
            [InlineKeyboardButton(text="📚 Сменить класс", callback_data="grade:change")],
        ]
    )


def leaderboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 Общий", callback_data="leaderboard:global"),
                InlineKeyboardButton(text="📚 Мой класс", callback_data="leaderboard:class"),
            ],
            [
                InlineKeyboardButton(
                    text="📅 За месяц", callback_data="leaderboard:monthly"
                )
            ],
            [InlineKeyboardButton(text="← Главное меню", callback_data="menu:main")],
        ]
    )
