from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bots.admin_bot import create_admin_bot, create_admin_dispatcher
from app.bots.user_bot import configure_user_bot, create_user_bot, create_user_dispatcher
from app.config.settings import Settings
from app.services.notification_service import NotificationService


@dataclass
class BotRuntime:
    user_bot: Bot
    admin_bot: Bot
    user_dispatcher: Dispatcher
    admin_dispatcher: Dispatcher
    tasks: list[asyncio.Task]

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.user_bot.session.close()
        await self.admin_bot.session.close()


async def start_bot_runtime(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> BotRuntime:
    user_bot = create_user_bot(settings)
    admin_bot = create_admin_bot(settings)
    notification_service = NotificationService(admin_bot, settings)
    user_dispatcher = create_user_dispatcher(
        settings, session_factory, notification_service
    )
    admin_dispatcher = create_admin_dispatcher(settings, session_factory)
    try:
        await configure_user_bot(user_bot)
    except Exception:
        await user_bot.session.close()
        await admin_bot.session.close()
        raise

    tasks = [
        asyncio.create_task(
            user_dispatcher.start_polling(user_bot, handle_signals=False),
            name="user-bot-polling",
        ),
        asyncio.create_task(
            admin_dispatcher.start_polling(admin_bot, handle_signals=False),
            name="admin-bot-polling",
        ),
    ]
    return BotRuntime(
        user_bot=user_bot,
        admin_bot=admin_bot,
        user_dispatcher=user_dispatcher,
        admin_dispatcher=admin_dispatcher,
        tasks=tasks,
    )
