"""
states.py — FSM стани бота.
"""

from aiogram.fsm.state import State, StatesGroup


class OperatorFSM(StatesGroup):
    menu = State()        # головне меню оператора
    job_detail = State()  # перегляд деталей замовлення


class OrderFSM(StatesGroup):
    waiting_for_file = State()   # очікування файлу
    configuring      = State()   # карточка показана, налаштування
    typing_copies    = State()   # ручний ввід кількості копій
    awaiting_payment = State()   # очікування оплати
