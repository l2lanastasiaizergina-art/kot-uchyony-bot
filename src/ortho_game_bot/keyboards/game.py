from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ortho_game_bot.database.models import ChoiceQuestion

from .callbacks import ChoiceAnswer


def game_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔎 Выбери верное написание",
                    callback_data="game:start:choice",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎧 Словарный диктант — скоро",
                    callback_data="game:dictation:soon",
                )
            ],
            [InlineKeyboardButton(text="← Главное меню", callback_data="menu:main")],
        ]
    )


def choice_keyboard(question: ChoiceQuestion) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(question.options):
        builder.button(
            text=option,
            callback_data=ChoiceAnswer(
                session_id=question.session_id,
                position=question.position,
                option=index,
            ),
        )
    builder.adjust(2, 2)
    return builder.as_markup()


def round_end_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Ещё раунд", callback_data="game:start:choice")],
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                InlineKeyboardButton(
                    text="🏆 Рейтинг", callback_data="leaderboard:global"
                ),
            ],
            [InlineKeyboardButton(text="← Главное меню", callback_data="menu:main")],
        ]
    )
