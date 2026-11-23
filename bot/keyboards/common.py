"""Keyboard building blocks shared by every screen."""
from collections.abc import Sequence
from typing import TypeVar

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import MenuCb

BTN_BACK = "⬅️ Назад"
BTN_HOME = "🏠 В головне меню"
MENU_MAIN = MenuCb(action="main").pack()

T = TypeVar("T")


def btn(text: str, data: CallbackData | str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data if isinstance(data, str) else data.pack())


def nav_row(back: CallbackData | str | None, home: CallbackData | str = MENU_MAIN) -> list[InlineKeyboardButton]:
    """The standard bottom row: «⬅️ Назад» (optional) + «🏠 В головне меню»."""
    row: list[InlineKeyboardButton] = []
    if back is not None:
        row.append(btn(BTN_BACK, back))
    row.append(btn(BTN_HOME, home))
    return row


def chunk(items: Sequence[T], size: int) -> list[list[T]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def markup(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(row) for row in rows if row])


def back_kb(back: CallbackData | str) -> InlineKeyboardMarkup:
    """Keyboard with navigation only (prompts, results)."""
    return markup(nav_row(back))
