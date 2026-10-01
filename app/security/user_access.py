from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import UserRepository


class ActiveUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text:
            if event.text.split(maxsplit=1)[0].split("@", maxsplit=1)[0] == "/start":
                return await handler(event, data)

        actor = getattr(event, "from_user", None)
        session: AsyncSession | None = data.get("session")
        if actor is None or session is None:
            return await handler(event, data)

        user = await UserRepository(session).get_by_telegram_id(actor.id)
        if user is None:
            text = "Send /start before using the bot."
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)
            return None
        if not user.is_active:
            text = "🚫 Your test account is disabled."
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)
            return None
        return await handler(event, data)

