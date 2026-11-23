"""Assembly of the root router. Order matters: the first router with a matching handler wins."""
from aiogram import Router

from bot.handlers import errors, fallback, info, my_bookings, start
from bot.handlers.admin.panel import build_admin_router
from bot.handlers.flow import CLIENT_FLOW, build_flow_router


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_routers(
        errors.router,
        build_admin_router(),  # admin-only, guarded by the IsAdmin filter
        start.router,  # /start, /menu, /cancel, «🏠 В головне меню» — before FSM text handlers
        build_flow_router(CLIENT_FLOW),
        my_bookings.router,
        info.router,
        fallback.router,  # catch-all, must stay last
    )
    return root
