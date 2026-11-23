"""FSM state groups."""
from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """Client booking flow. Member names must match AdminAddStates (shared flow code)."""

    service = State()
    master = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


class AdminAddStates(StatesGroup):
    """Admin adds a booking manually (same steps as the client flow)."""

    service = State()
    master = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


class AdminScheduleStates(StatesGroup):
    wait_date = State()


class AdminCatalogStates(StatesGroup):
    service_name = State()
    service_price = State()
    service_duration = State()
    master_name = State()
    edit_value = State()
    day_hours = State()


class AdminTimeOffStates(StatesGroup):
    date = State()
    scope = State()
    hours = State()


class AdminBroadcastStates(StatesGroup):
    text = State()
    confirm = State()
