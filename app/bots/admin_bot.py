from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bots.client import create_telegram_bot
from app.bots.handlers.admin import build_admin_router
from app.bots.middleware import DatabaseSessionMiddleware
from app.config.settings import Settings
from app.security.authorization import AdminAuthorizationMiddleware


def create_admin_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    router = build_admin_router(settings)
    authorization = AdminAuthorizationMiddleware(settings)
    session_middleware = DatabaseSessionMiddleware(session_factory)
    router.message.outer_middleware(authorization)
    router.callback_query.outer_middleware(authorization)
    router.message.outer_middleware(session_middleware)
    router.callback_query.outer_middleware(session_middleware)
    dispatcher.include_router(router)
    return dispatcher


def create_admin_bot(settings: Settings) -> Bot:
    return create_telegram_bot(settings.admin_bot_token.get_secret_value())
