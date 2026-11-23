"""«Послуги та ціни» and «Контакти та адреса»."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot import texts
from bot.callbacks import MenuCb
from bot.context import AppContext
from bot.handlers.helpers import edit_or_send
from bot.keyboards.client import contacts_kb, services_info_kb

logger = logging.getLogger(__name__)
router = Router(name="info")


@router.callback_query(MenuCb.filter(F.action == "services"))
async def show_services_and_prices(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    services = await ctx.catalog.list_services()
    await edit_or_send(cb, texts.services_info(services), services_info_kb())


@router.callback_query(MenuCb.filter(F.action == "contacts"))
async def show_contacts(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    settings = ctx.settings
    await edit_or_send(
        cb,
        texts.contacts(settings.salon_name, settings.salon_address, settings.salon_phone, settings.salon_hours),
        contacts_kb(settings.salon_map_url),
    )
    if settings.salon_lat is not None and settings.salon_lon is not None:
        try:
            await cb.bot.send_location(cb.from_user.id, settings.salon_lat, settings.salon_lon)
        except TelegramAPIError:
            logger.warning("Could not send the salon location", exc_info=True)
