"""Repositories: all SQL lives here."""
from bot.database.repositories.appointments import AppointmentRepo
from bot.database.repositories.catalog import CatalogRepo
from bot.database.repositories.schedule import ScheduleRepo
from bot.database.repositories.users import UserRepo

__all__ = ["AppointmentRepo", "CatalogRepo", "ScheduleRepo", "UserRepo"]
