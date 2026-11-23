"""Admin screens used by several admin modules (leaf module: imports no routers)."""
from bot import texts
from bot.context import AppContext
from bot.handlers.helpers import Target, render
from bot.keyboards.admin import admin_menu_kb


async def show_admin_menu(target: Target, ctx: AppContext) -> None:
    users = await ctx.users.count()
    upcoming = await ctx.appointments.count_upcoming(ctx.booking.now())
    await render(target, texts.admin_menu(users, upcoming), admin_menu_kb())
