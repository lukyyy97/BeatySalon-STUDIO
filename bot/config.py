"""Application settings loaded from environment variables / .env file."""
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _split_ids(value: str) -> list[str]:
    return [token for token in re.split(r"[,\s;]+", value) if token]


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden via `.env`."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    bot_token: SecretStr
    admin_ids_raw: str = Field(default="", validation_alias="ADMIN_IDS")

    db_path: Path = Path("data/salon.db")
    timezone: str = "Europe/Kyiv"
    log_level: str = "INFO"

    booking_horizon_days: int = Field(default=14, ge=1, le=60)
    slot_step_min: int = Field(default=30, ge=5, le=240)
    min_lead_minutes: int = Field(default=60, ge=0, le=1440)

    salon_name: str = "Beauty Studio"
    salon_address: str = "м. Київ, вул. Хрещатик, 1"
    salon_phone: str = "+380 44 123 45 67"
    salon_hours: str = "Пн–Сб: 09:00–19:00, Нд: вихідний"
    salon_map_url: str = ""
    salon_lat: float | None = None
    salon_lon: float | None = None

    @field_validator("admin_ids_raw")
    @classmethod
    def _validate_admin_ids(cls, value: str) -> str:
        for token in _split_ids(value):
            if not re.fullmatch(r"\d+", token):
                raise ValueError(f"ADMIN_IDS must contain only numeric Telegram IDs, got {token!r}")
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value!r}") from exc
        return value

    @field_validator("db_path")
    @classmethod
    def _absolute_db_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else BASE_DIR / value

    @field_validator("salon_lat", "salon_lon", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @property
    def admin_ids(self) -> frozenset[int]:
        return frozenset(int(token) for token in _split_ids(self.admin_ids_raw))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
