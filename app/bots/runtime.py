from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bots.admin_bot import create_admin_bot, create_admin_dispatcher
from app.bots.user_bot import configure_user_bot, create_user_bot, create_user_dispatcher
from app.config.settings import Settings
from app.services.chain_watchers import EvmWatcher, SolanaWatcher
from app.services.deposit_service import DepositService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


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
    notification_service = NotificationService(admin_bot, settings, user_bot=user_bot)
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
    if settings.deposit_watchers_enabled:
        deposits = DepositService(session_factory, notification_service)
        try:
            await deposits.resend_unnotified()
        except Exception as exc:
            logger.warning("Failed to resend unnotified deposits: %s", exc)
        watchers = [
            EvmWatcher(
                chain="ethereum", rpc_url=settings.rpc_url("ethereum"), service=deposits,
                confirmations=settings.eth_deposit_confirmations,
                poll_seconds=settings.deposit_poll_seconds,
            ),
            EvmWatcher(
                chain="bnb", rpc_url=settings.rpc_url("bnb"), service=deposits,
                confirmations=settings.bnb_deposit_confirmations, poa=True,
                poll_seconds=settings.deposit_poll_seconds,
            ),
            SolanaWatcher(rpc_url=settings.rpc_url("solana"), service=deposits),
        ]
        tasks += [
            asyncio.create_task(w.run(), name=f"deposit-watcher-{w.chain}") for w in watchers
        ]
    return BotRuntime(
        user_bot=user_bot,
        admin_bot=admin_bot,
        user_dispatcher=user_dispatcher,
        admin_dispatcher=admin_dispatcher,
        tasks=tasks,
    )
