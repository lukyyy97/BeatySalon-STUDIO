"""Admin entry point (/admin), main admin menu and assembly of the admin router."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks import AdmMenuCb
from bot.context import AppContext
from bot.filters import IsAdmin
from bot.handlers import flow
from bot.handlers.admin import broadcast, catalog, schedule, timeoff
from bot.handlers.admin.views import show_admin_menu
from bot.handlers.helpers import drop_reply_keyboard_if_needed

router = Router(name="admin_panel")


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await drop_reply_keyboard_if_needed(message, state)
    await state.clear()
    await show_admin_menu(message, ctx)


@router.callback_query(AdmMenuCb.filter(F.action == "main"))
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await show_admin_menu(cb, ctx)


@router.callback_query(AdmMenuCb.filter(F.action == "add"))
async def cb_add_booking(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await cb.answer()
    await flow.start_flow(cb, state, ctx, flow.ADMIN_FLOW)


def build_admin_router() -> Router:
    """Everything below is reachable only for users listed in ADMIN_IDS."""
    admin = Router(name="admin")
    admin.message.filter(IsAdmin())
    admin.callback_query.filter(IsAdmin())
    admin.include_routers(
        router,
        flow.build_flow_router(flow.ADMIN_FLOW),
        schedule.router,
        catalog.router,
        timeoff.router,
        broadcast.router,
    )
    return admin
