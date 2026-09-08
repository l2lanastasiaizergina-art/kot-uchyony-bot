from aiogram.fsm.state import State, StatesGroup


class GameStates(StatesGroup):
    choosing_mode = State()
    answering_dictation = State()
    answering_choice = State()
    showing_result = State()


class AdminStates(StatesGroup):
    uploading_words = State()
    composing_broadcast = State()
    scheduling_quiz = State()

