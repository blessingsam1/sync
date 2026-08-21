from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import Response, TelegramMethod
from aiogram.methods.base import TelegramType


class TelegramRequestRetryMiddleware(BaseRequestMiddleware):
    def __init__(self, attempts: int = 3, retry_delay: float = 1.0) -> None:
        self.attempts = max(1, attempts)
        self.retry_delay = max(0.0, retry_delay)

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        if method.__api_method__ == "getUpdates":
            return await make_request(bot, method)

        for attempt in range(self.attempts):
            try:
                return await make_request(bot, method)
            except TelegramNetworkError:
                if attempt == self.attempts - 1:
                    raise
                delay = self.retry_delay * (2**attempt)
                if delay:
                    await asyncio.sleep(delay)

        raise RuntimeError("Telegram request retry loop exited unexpectedly")


def create_telegram_bot(token: str) -> Bot:
    session = AiohttpSession(timeout=120)
    session.middleware(TelegramRequestRetryMiddleware())
    return Bot(token=token, session=session)
