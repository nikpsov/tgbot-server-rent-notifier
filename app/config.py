import logging
import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_chat_id: int
    timezone: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN")
    owner_raw = os.getenv("OWNER_CHAT_ID")
    timezone = os.getenv("TZ", "Europe/Moscow")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if not owner_raw:
        raise RuntimeError("OWNER_CHAT_ID is required")

    try:
        owner_chat_id = int(owner_raw)
    except ValueError as exc:
        raise RuntimeError("OWNER_CHAT_ID must be integer") from exc

    return Settings(bot_token=bot_token, owner_chat_id=owner_chat_id, timezone=timezone)


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("rent_notifier")


def configure_timezone(tz_name: str) -> None:
    os.environ["TZ"] = tz_name
    try:
        time.tzset()  # type: ignore[attr-defined]
    except AttributeError:
        pass
