from aiogram.filters.callback_data import CallbackData


class ChoiceAnswer(CallbackData, prefix="answer"):
    session_id: str
    position: int
    option: int
