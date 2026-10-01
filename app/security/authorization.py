from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config.settings import Settings


def is_admin(telegram_id: int | None, settings: Settings) -> bool:
    return telegram_id is not None and telegram_id in settings.admin_telegram_ids


class AdminAuthorizationMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        actor = getattr(event, "from_user", None)
        if not is_admin(getattr(actor, "id", None), self.settings):
            if isinstance(event, CallbackQuery):
                await event.answer("❌ Unauthorized.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("❌ Unauthorized.")
            return None
        return await handler(event, data)
