from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonCommands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bots.client import create_telegram_bot
from app.bots.handlers.user import build_user_router
from app.bots.middleware import DatabaseSessionMiddleware
from app.config.settings import Settings
from app.security.user_access import ActiveUserMiddleware
from app.services.notification_service import NotificationService


USER_BOT_COMMANDS = [
    BotCommand(command="start", description="Start the bot"),
    BotCommand(command="help", description="View the bot guide"),
    BotCommand(command="wallet", description="View your wallet"),
    BotCommand(command="withdraw", description="Withdraw your funds"),
    BotCommand(command="settings", description="Open settings"),
]

USER_BOT_SHORT_DESCRIPTION = "Degen, copytrade and autotrade assistant."

USER_BOT_DESCRIPTION = (
    "⚡ CopyEntry Bot is a lightning-fast Telegram trading assistant built for "
    "serious traders. It lets you autotrade instantly, copytrade top wallets in "
    "real time, and snipe new tokens the moment they launch. With CopyFlow, you "
    "never miss an opportunity - fast, precise, and effortless trading, all "
    "inside Telegram."
)


def create_user_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    notification_service: NotificationService,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    router = build_user_router(settings, notification_service)
    session_middleware = DatabaseSessionMiddleware(session_factory)
    router.message.outer_middleware(session_middleware)
    router.callback_query.outer_middleware(session_middleware)
    router.message.middleware(ActiveUserMiddleware())
    router.callback_query.middleware(ActiveUserMiddleware())
    dispatcher.include_router(router)
    return dispatcher


def create_user_bot(settings: Settings) -> Bot:
    return create_telegram_bot(settings.user_bot_token.get_secret_value())


async def configure_user_bot(bot: Bot) -> None:
    await bot.set_my_commands(USER_BOT_COMMANDS)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await bot.set_my_short_description(USER_BOT_SHORT_DESCRIPTION)
    await bot.set_my_description(USER_BOT_DESCRIPTION)
