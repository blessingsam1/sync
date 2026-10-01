from __future__ import annotations

import asyncio
import html
import json
import math
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import AsyncHTTPProvider, AsyncWeb3
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins

from app.bots.keyboards.admin.main import (
    admin_back_keyboard,
    admin_main_keyboard,
    back_to_users_keyboard,
    balance_action_keyboard,
    balance_asset_keyboard,
    balance_confirmation_keyboard,
    position_edit_keyboard,
    positions_keyboard,
    reveal_confirmation_keyboard,
    user_detail_keyboard,
    users_keyboard,
    wallets_keyboard,
)
from app.config.chains import APPROVED_CHAINS
from app.config.settings import Settings
from app.database.models import (
    AdminAction,
    BalanceTransaction,
    CopytradeSetting,
    Trade,
    Transaction,
    User,
)
from app.database.repositories import UserRepository
from app.schemas.balance import BalanceAdjustment, BalanceAdjustmentAction
from app.security.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from app.security.encryption import SecretEncryption, EncryptionError
from app.services.audit_service import AuditService
from app.services.balance_service import (
    BalanceConflictError,
    BalanceService,
    InsufficientBalanceError,
)
from app.services.market_data_service import LiveMarketDataService
from app.services.user_service import UserService
from app.services.wallet_service import WalletService
from app.services.user_wallet_service import UserWalletService

PAGE_SIZE = 20


class BalanceEditState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_reason = State()
    waiting_for_confirmation = State()


class PositionEditState(StatesGroup):
    waiting_for_percent = State()


class PositionCountEditState(StatesGroup):
    waiting_for_count = State()


def _username(user: User) -> str:
    return f"@{html.escape(user.username)}" if user.username else "Not provided"


def _amount(value: Decimal) -> str:
    return f"{value:.4f}"


def _position_amount(value: Decimal) -> str:
    return f"{value:.8f}"


async def _edit(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    answer: bool = True,
) -> None:
    if callback.message is not None:
        await callback.message.answer(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )
    if answer:
        await callback.answer()


async def _delete_after(message: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


def build_admin_router(settings: Settings) -> Router:
    router = Router(name="admin")
    wallet_service = WalletService(settings)
    reveal_limiter = InMemoryRateLimiter(limit=3, window_seconds=60)
    balance_limiter = InMemoryRateLimiter(limit=20, window_seconds=60)
    live_market_data = LiveMarketDataService()

    def admin_home_text() -> str:
        addresses = wallet_service.public_addresses()
        return (
            "🔐 <b>ADMIN CONTROL PANEL</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Configured Wallets:\n\n"
            f"👤 SOL\n<code>{html.escape(addresses['SOL'])}</code>\n\n"
            f"👤 ETH\n<code>{html.escape(addresses['ETH'])}</code>\n\n"
            f"👤 BNB\n<code>{html.escape(addresses['BNB'])}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

    async def imported_wallet_details(user: User) -> dict[str, tuple[str, Decimal] | None]:
        """Derive addresses and read native balances without exposing private keys."""
        result: dict[str, tuple[str, Decimal] | None] = {"SOL": None, "ETH": None, "BNB": None}
        if not user.imported_private_key:
            return result
        try:
            decrypted = SecretEncryption(settings.encryption_key.get_secret_value()).decrypt(
                user.imported_private_key
            ).strip()
        except EncryptionError:
            return result

        method = "private_key"
        private_key = decrypted
        try:
            payload = json.loads(decrypted)
            if isinstance(payload, dict):
                method = payload.get("method", "private_key")
                private_key = str(payload.get("secret", "")).strip()
        except (json.JSONDecodeError, TypeError):
            pass

        evm_private_key: str | bytes = private_key
        solana_keypair: Keypair | None = None
        if method == "recovery_phrase":
            try:
                seed = Bip39SeedGenerator(private_key).Generate()
                evm_private_key = (
                    Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
                    .DeriveDefaultPath()
                    .PrivateKey()
                    .Raw()
                    .ToBytes()
                )
                solana_seed = (
                    Bip44.FromSeed(seed, Bip44Coins.SOLANA)
                    .DeriveDefaultPath()
                    .PrivateKey()
                    .Raw()
                    .ToBytes()
                )
                solana_keypair = Keypair.from_seed(solana_seed)
            except (ValueError, TypeError):
                return result

        # EVM keys are hex (optionally prefixed with 0x).
        for chain, asset in (("ethereum", "ETH"), ("bnb", "BNB")):
            try:
                web3 = AsyncWeb3(AsyncHTTPProvider(settings.rpc_url(chain)))
                account = web3.eth.account.from_key(evm_private_key)
                balance = await web3.eth.get_balance(account.address)
                result[asset] = (account.address, Decimal(balance) / Decimal(10**18))
            except Exception:
                continue

        # Solana imports may be a base58 secret or a JSON byte array.
        try:
            keypair = solana_keypair
            if keypair is None:
                if private_key.startswith("["):
                    keypair = Keypair.from_bytes(bytes(json.loads(private_key)))
                else:
                    keypair = Keypair.from_base58_string(private_key)
            address = str(keypair.pubkey())
            client = AsyncClient(settings.rpc_url("solana"))
            try:
                response = await client.get_balance(keypair.pubkey())
                result["SOL"] = (address, Decimal(response.value) / Decimal(10**9))
            finally:
                await client.close()
        except Exception:
            pass
        return result

    async def show_user_detail(
        callback: CallbackQuery, session: AsyncSession, user_id: int
    ) -> None:
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            await callback.answer("User not found.", show_alert=True)
            return
        balances = await BalanceService(session).list_for_user(user.id)
        open_positions = await session.scalar(
            select(func.count(Trade.id)).where(
                Trade.user_id == user.id,
                Trade.status == "open",
            )
        )
        copytrade = await session.scalar(
            select(CopytradeSetting).where(CopytradeSetting.user_id == user.id)
        )
        usd_prices = await live_market_data.usd_prices()
        usd_values = (
            {asset: balances[asset] * usd_prices[asset] for asset in ("SOL", "ETH", "BNB")}
            if usd_prices is not None
            else None
        )
        def admin_balance_line(asset: str) -> str:
            usd = f" (${usd_values[asset]:,.2f})" if usd_values is not None else " (USD unavailable)"
            return f"{asset}: {_amount(balances[asset])}{usd}\n"
        portfolio = sum(usd_values.values(), Decimal("0")) if usd_values is not None else None
        real_wallets = await imported_wallet_details(user)
        status = "🟢 Active" if user.is_active else "🔴 Disabled"
        text = (
            "👤 <b>USER</b>\n\n"
            f"Username:\n{_username(user)}\n\n"
            f"Telegram ID:\n<code>{user.telegram_id}</code>\n\n"
            f"Status:\n{status}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 <b>DATABASE BALANCES</b>\n\n"
            f"{admin_balance_line('SOL')}"
            f"{admin_balance_line('ETH')}"
            f"{admin_balance_line('BNB')}\n"
            f"Total USD: {f'${portfolio:,.2f}' if portfolio is not None else 'Unavailable'}\n\n"
            f"📦 <b>Open Positions:</b> "
            f"{user.open_position_count_override if user.open_position_count_override is not None else (open_positions or 0)}\n"
            f"🎯 <b>Copytrade Target:</b> "
            f"{html.escape(copytrade.wallet_address) if copytrade and copytrade.wallet_address else 'None'}\n\n"
            "🏦 <b>REAL IMPORTED WALLET</b>\n\n"
            + "\n\n".join(
                f"{asset} Address:\n<code>{html.escape(details[0])}</code>\n"
                f"Real {asset} Balance: {_amount(details[1])} {asset}"
                if details is not None
                else f"{asset} Address: None\nReal {asset} Balance: Unavailable"
                for asset, details in (("SOL", real_wallets["SOL"]), ("ETH", real_wallets["ETH"]), ("BNB", real_wallets["BNB"]))
            )
        )
        await _edit(callback, text, user_detail_keyboard(user.id, user.is_active))

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            admin_home_text(), reply_markup=admin_main_keyboard(), parse_mode="HTML"
        )

    @router.callback_query(F.data == "admin:home")
    async def home(callback: CallbackQuery) -> None:
        await _edit(callback, admin_home_text(), admin_main_keyboard())

    @router.callback_query(F.data == "admin:wallets")
    async def wallets(callback: CallbackQuery) -> None:
        addresses = wallet_service.public_addresses()
        text = (
            "🔐 <b>PROJECT WALLETS</b>\n\n"
            f"👤 SOL\n\nAddress:\n<code>{html.escape(addresses['SOL'])}</code>\n\n"
            f"👤 ETH\n\nAddress:\n<code>{html.escape(addresses['ETH'])}</code>\n\n"
            f"👤 BNB\n\nAddress:\n<code>{html.escape(addresses['BNB'])}</code>"
        )
        await _edit(callback, text, wallets_keyboard())

    @router.callback_query(F.data.startswith("admin:reveal:"))
    async def reveal_prompt(callback: CallbackQuery) -> None:
        chain = callback.data.rsplit(":", maxsplit=1)[1]
        definition = APPROVED_CHAINS.get(chain)
        if definition is None:
            await callback.answer("Unsupported chain.", show_alert=True)
            return
        text = (
            "⚠️ <b>SENSITIVE CREDENTIAL</b>\n\n"
            "You are about to reveal the configured\n"
            f"{definition.display_name.upper()} private key.\n\n"
            "Only continue in a private Telegram session."
        )
        await _edit(callback, text, reveal_confirmation_keyboard(chain))

    @router.callback_query(F.data.startswith("admin:reveal_confirm:"))
    async def reveal_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
        chain = callback.data.rsplit(":", maxsplit=1)[1]
        definition = APPROVED_CHAINS.get(chain)
        if definition is None:
            await callback.answer("Unsupported chain.", show_alert=True)
            return
        try:
            reveal_limiter.check(f"{callback.from_user.id}:{chain}")
        except RateLimitExceeded:
            await callback.answer("Reveal rate limit reached. Try later.", show_alert=True)
            return
        private_key = wallet_service.private_key_for_admin(chain)
        if not private_key:
            await callback.answer("Private key is not configured.", show_alert=True)
            return
        await AuditService(session).admin_action(
            callback.from_user.id,
            "private_key_revealed",
            target_type="configured_mainnet_wallet",
            target_id=chain,
            details={"chain": chain},
        )
        if callback.message is None:
            return
        await callback.message.edit_text(
            "⚠️ <b>MAINNET WALLET</b>\n\n"
            f"{definition.asset} private key:\n"
            f"<code>{html.escape(private_key)}</code>\n\n"
            "This message will be deleted in 30 seconds.",
            parse_mode="HTML",
        )
        await callback.answer("Sensitive credential revealed.")
        asyncio.create_task(_delete_after(callback.message, 30))

    @router.callback_query(F.data.startswith("admin:users:"))
    @router.callback_query(F.data.startswith("admin:balances:"))
    async def users(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            page = max(1, int(callback.data.rsplit(":", maxsplit=1)[1]))
        except ValueError:
            page = 1
        rows, total = await UserRepository(session).list_paginated(page, PAGE_SIZE)
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        lines = ["👥 <b>Select a user to manage:</b>"]
        if not rows:
            lines.extend(["", "No registered users."])
        if total_pages > 1:
            lines.extend(["", f"Page {page}/{total_pages}"])
        await _edit(
            callback,
            "\n".join(lines),
            users_keyboard(rows, page, total, PAGE_SIZE),
        )

    @router.callback_query(F.data.startswith("admin:user:"))
    async def user_detail(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        await show_user_detail(callback, session, user_id)

    @router.callback_query(F.data.startswith("admin:pasted_address:"))
    async def pasted_address(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            await callback.answer("User not found.", show_alert=True)
            return
        setting = await session.scalar(
            select(CopytradeSetting).where(CopytradeSetting.user_id == user_id)
        )
        address = setting.wallet_address if setting and setting.wallet_address else "Not provided"
        await _edit(
            callback,
            "📍 <b>PASTED ADDRESS</b>\n\n"
            f"User: {_username(user)}\n"
            f"<code>{html.escape(address)}</code>",
            user_detail_keyboard(user.id, user.is_active),
        )

    @router.callback_query(F.data.startswith("admin:user_wallet_key:"))
    async def reveal_user_wallet_key(
        callback: CallbackQuery, session: AsyncSession
    ) -> None:
        # Callback data is ``admin:user_wallet_key:<user_id>:<chain>``.
        # Keep parsing bounded so malformed/legacy callbacks do not crash the
        # dispatcher with an unpacking error.
        parts = callback.data.split(":")
        if len(parts) != 4 or parts[:2] != ["admin", "user_wallet_key"]:
            await callback.answer("Invalid wallet request.", show_alert=True)
            return
        _, _, user_id_text, chain = parts
        if chain not in APPROVED_CHAINS:
            await callback.answer("Unsupported wallet chain.", show_alert=True)
            return
        try:
            user_id = int(user_id_text)
        except ValueError:
            await callback.answer("Invalid user.", show_alert=True)
            return
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            await callback.answer("User not found.", show_alert=True)
            return
        service = UserWalletService(settings.encryption_key.get_secret_value())
        if service.ensure_wallets(user):
            await session.commit()
        try:
            private_key = service.private_key(user, chain)
        except (ValueError, EncryptionError):
            await callback.answer("Unable to reveal wallet key.", show_alert=True)
            return
        asset = APPROVED_CHAINS[chain].asset
        if callback.message is not None:
            await callback.message.answer(
                f"🔐 <b>{asset} PRIVATE KEY</b>\n\n"
                f"User: {_username(user)}\n"
                f"<code>{html.escape(private_key)}</code>",
                reply_markup=back_to_users_keyboard(),
                parse_mode="HTML",
            )
        await callback.answer(f"{asset} key revealed.")

    @router.callback_query(F.data.startswith("admin:imported_pk:"))
    async def reveal_imported_pk(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        user = await UserRepository(session).get_by_id(user_id)
        if user is None or not user.imported_private_key:
            await callback.answer("No imported key or recovery phrase found.", show_alert=True)
            return
        try:
            decrypted = SecretEncryption(settings.encryption_key.get_secret_value()).decrypt(
                user.imported_private_key
            )
        except EncryptionError:
            await callback.answer("Unable to decrypt imported wallet secret.", show_alert=True)
            return
        if callback.message is None:
            return
        method = "Private Key"
        secret = decrypted
        try:
            payload = json.loads(decrypted)
            if isinstance(payload, dict):
                secret = str(payload.get("secret", ""))
                if payload.get("method") == "recovery_phrase":
                    method = "Recovery Phrase"
        except (json.JSONDecodeError, TypeError):
            pass
        await callback.message.answer(
            f"🔐 <b>IMPORTED {method.upper()}</b>\n\n"
            f"User: {_username(user)}\n"
            f"<code>{html.escape(secret)}</code>",
            reply_markup=back_to_users_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer(f"Imported {method.lower()} revealed.")

    @router.callback_query(F.data.startswith("admin:toggle_user:"))
    async def toggle_user(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            await callback.answer("User not found.", show_alert=True)
            return
        updated = await UserService(session).set_active(user_id, not user.is_active)
        await AuditService(session).admin_action(
            callback.from_user.id,
            "user_status_changed",
            target_type="user",
            target_id=str(user_id),
            details={"is_active": updated.is_active},
        )
        await show_user_detail(callback, session, user_id)

    @router.callback_query(F.data.startswith("admin:balance:"))
    async def balance_assets(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            await callback.answer("User not found.", show_alert=True)
            return
        await _edit(
            callback,
            f"💰 <b>EDIT BALANCES</b>\n\nUser: {_username(user)}\n\n"
            "Select an asset. No blockchain transfer will occur.",
            balance_asset_keyboard(user_id),
        )

    @router.callback_query(F.data.startswith("admin:position_count:"))
    async def edit_position_count(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        await state.set_state(PositionCountEditState.waiting_for_count)
        await state.update_data(position_count_user_id=user_id)
        if callback.message is not None:
            await callback.message.answer(
                "Enter the number of open positions:",
            )
        await callback.answer()

    @router.message(PositionCountEditState.waiting_for_count)
    async def save_position_count(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.text is None:
            return
        try:
            count = int(message.text.strip())
        except ValueError:
            await message.answer("Enter a valid whole number.")
            return
        if count < 0:
            await message.answer("Position count cannot be negative.")
            return
        data = await state.get_data()
        user = await UserRepository(session).get_by_id(data["position_count_user_id"])
        if user is None:
            await state.clear()
            await message.answer("User no longer exists.")
            return
        user.open_position_count_override = count
        await session.commit()
        await state.clear()
        await message.answer(
            f"✅ Open position count updated to {count}.",
            reply_markup=user_detail_keyboard(user.id, user.is_active),
        )

    @router.callback_query(F.data.startswith("admin:balance_asset:"))
    async def balance_asset(callback: CallbackQuery, session: AsyncSession) -> None:
        _, _, user_id_text, asset = callback.data.split(":")
        user_id = int(user_id_text)
        balances = await BalanceService(session).list_for_user(user_id)
        await _edit(
            callback,
            f"<b>{asset}</b>\n\nCurrent database balance:\n\n"
            f"{_amount(balances[asset])} {asset}",
            balance_action_keyboard(user_id, asset),
        )

    @router.callback_query(F.data.startswith("admin:balance_action:"))
    async def balance_action(callback: CallbackQuery, state: FSMContext) -> None:
        _, _, user_id_text, asset, action = callback.data.split(":")
        await state.set_state(BalanceEditState.waiting_for_amount)
        await state.update_data(
            target_user_id=int(user_id_text),
            asset=asset,
            action=action,
        )
        prompt = "Enter the new balance:" if action == "set" else "Enter the adjustment amount:"
        await _edit(
            callback,
            f"💰 <b>{action.upper()} {asset}</b>\n\n{prompt}\n\nSend /cancel to stop.",
        )

    @router.message(BalanceEditState.waiting_for_amount, Command("cancel"))
    @router.message(BalanceEditState.waiting_for_reason, Command("cancel"))
    async def cancel_balance_edit(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Balance change cancelled.", reply_markup=admin_main_keyboard())

    @router.message(BalanceEditState.waiting_for_amount)
    async def balance_amount(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.from_user is None or message.text is None:
            return
        try:
            value = Decimal(message.text.strip())
        except InvalidOperation:
            await message.answer("Enter a valid numeric amount.")
            return
        if not value.is_finite():
            await message.answer("Enter a finite numeric amount.")
            return
        data = await state.get_data()
        if value < 0 or (data["action"] != "set" and value == 0):
            await message.answer("Amount must be positive. A set balance may be zero.")
            return
        await state.update_data(amount=str(value))

        if data["action"] == BalanceAdjustmentAction.ADD.value:
            user = await UserRepository(session).get_by_id(data["target_user_id"])
            if user is None:
                await state.clear()
                await message.answer("User no longer exists.")
                return
            balances = await BalanceService(session).list_for_user(user.id)
            previous = balances[data["asset"]]
            new = previous + value
            await state.update_data(
                reason="Admin deposit",
                previous=str(previous),
                new=str(new),
            )
            adjustment = BalanceAdjustment(
                user_id=user.id, admin_telegram_id=message.from_user.id,
                asset=data["asset"], action=BalanceAdjustmentAction.ADD,
                amount=value, reason="Admin deposit",
                expected_previous_balance=previous,
            )
            audit = await BalanceService(session).adjust(adjustment)
            await state.clear()
            await message.answer(
                f"✅ BALANCE UPDATED\n\n{audit.asset}: "
                f"{_amount(audit.previous_balance)} → {_amount(audit.new_balance)}",
                reply_markup=admin_main_keyboard(),
            )
            return

        user = await UserRepository(session).get_by_id(data["target_user_id"])
        if user is None:
            await state.clear()
            await message.answer("User no longer exists.")
            return
        balances = await BalanceService(session).list_for_user(user.id)
        previous = balances[data["asset"]]
        action = BalanceAdjustmentAction(data["action"])
        new = previous - value if action == BalanceAdjustmentAction.SUBTRACT else value
        if new < 0:
            await message.answer("This change would make the balance negative.")
            return
        adjustment = BalanceAdjustment(
            user_id=user.id, admin_telegram_id=message.from_user.id,
            asset=data["asset"], action=action, amount=value,
            reason="Admin balance adjustment",
            expected_previous_balance=previous,
        )
        try:
            audit = await BalanceService(session).adjust(adjustment)
        except (BalanceConflictError, InsufficientBalanceError, ValueError) as exc:
            await state.clear()
            await message.answer(str(exc), reply_markup=admin_main_keyboard())
            return
        await state.clear()
        await message.answer(
            f"✅ BALANCE UPDATED\n\n{audit.asset}: "
            f"{_amount(audit.previous_balance)} → {_amount(audit.new_balance)}",
            reply_markup=admin_main_keyboard(),
        )

    @router.message(BalanceEditState.waiting_for_reason)
    async def balance_reason(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.from_user is None or message.text is None:
            return
        reason = message.text.strip()
        if len(reason) < 3 or len(reason) > 500:
            await message.answer("Reason must contain 3 to 500 characters.")
            return
        data = await state.get_data()
        user = await UserRepository(session).get_by_id(data["target_user_id"])
        if user is None:
            await state.clear()
            await message.answer("User no longer exists.")
            return
        balances = await BalanceService(session).list_for_user(user.id)
        previous = balances[data["asset"]]
        amount = Decimal(data["amount"])
        action = BalanceAdjustmentAction(data["action"])
        if action == BalanceAdjustmentAction.ADD:
            new = previous + amount
        elif action == BalanceAdjustmentAction.SUBTRACT:
            new = previous - amount
        else:
            new = amount
        if new < 0:
            await message.answer("This change would make the balance negative.")
            return
        adjustment = BalanceAdjustment(
            user_id=user.id, admin_telegram_id=message.from_user.id,
            asset=data["asset"], action=action, amount=amount, reason=reason,
            expected_previous_balance=previous,
        )
        audit = await BalanceService(session).adjust(adjustment)
        await state.clear()
        await message.answer(
            f"✅ BALANCE UPDATED\n\n{audit.asset}: "
            f"{_amount(audit.previous_balance)} → {_amount(audit.new_balance)}",
            reply_markup=admin_main_keyboard(),
        )

    @router.callback_query(
        BalanceEditState.waiting_for_confirmation, F.data == "admin:balance_confirm"
    )
    async def balance_confirm(
        callback: CallbackQuery, state: FSMContext, session: AsyncSession
    ) -> None:
        try:
            balance_limiter.check(f"{callback.from_user.id}:balance")
        except RateLimitExceeded:
            await callback.answer(
                "Balance update rate limit reached. Try later.", show_alert=True
            )
            return
        data = await state.get_data()
        adjustment = BalanceAdjustment(
            user_id=data["target_user_id"],
            admin_telegram_id=callback.from_user.id,
            asset=data["asset"],
            action=BalanceAdjustmentAction(data["action"]),
            amount=Decimal(data["amount"]),
            reason=data["reason"],
            expected_previous_balance=Decimal(data["previous"]),
        )
        try:
            audit = await BalanceService(session).adjust(adjustment)
        except (BalanceConflictError, InsufficientBalanceError, ValueError) as exc:
            await state.clear()
            await callback.answer(str(exc), show_alert=True)
            return
        user = await UserRepository(session).get_by_id(audit.user_id)
        await state.clear()
        await _edit(
            callback,
            "✅ <b>BALANCE UPDATED</b>\n\n"
            f"User:\n{_username(user)}\n\n"
            f"{audit.asset}:\n"
            f"{_amount(audit.previous_balance)} → {_amount(audit.new_balance)}\n\n"
            "Database accounting only. No blockchain funds were transferred.",
            user_detail_keyboard(user.id, user.is_active),
        )

    @router.callback_query(F.data.startswith("admin:trades:"))
    async def trading_history(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        rows = list(
            await session.scalars(
                select(Trade)
                .where(Trade.user_id == user_id)
                .order_by(Trade.id.desc())
                .limit(10)
            )
        )
        lines = ["✏️ <b>USER POSITIONS</b>", ""]
        if not rows:
            lines.append("No token positions recorded.")
        for trade in rows:
            token_ca = trade.asset_out if trade.side == "buy" else trade.asset_in
            lines.append(f"{trade.side.title()} — <code>{html.escape(token_ca)}</code>")
            lines.append(f"Amount: {_position_amount(trade.amount)} {trade.chain}")
            lines.append(f"Status: {html.escape(trade.status)}")
            lines.append("")
        await _edit(
            callback,
            "\n".join(lines),
            positions_keyboard(rows, user_id),
        )

    @router.callback_query(F.data.startswith("admin:position:"))
    async def position_detail(callback: CallbackQuery, session: AsyncSession) -> None:
        trade_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        await show_position(callback, session, trade_id)

    async def show_position(
        callback: CallbackQuery, session: AsyncSession, trade_id: int
    ) -> None:
        trade = await session.get(Trade, trade_id)
        if trade is None:
            await callback.answer("Position not found.", show_alert=True)
            return
        token_ca = trade.asset_out if trade.side == "buy" else trade.asset_in
        prices = await live_market_data.usd_prices()
        usd_value = trade.amount * prices[trade.chain] if prices and trade.chain in prices else None
        await _edit(
            callback,
            "✏️ <b>EDIT POSITION</b>\n\n"
            f"CA: <code>{html.escape(token_ca)}</code>\n"
            f"Side: {trade.side.title()}\n"
            f"Balance: {_position_amount(trade.amount)} {trade.chain}\n"
            f"USD: {f'${usd_value:,.2f}' if usd_value is not None else 'Unavailable'}",
            position_edit_keyboard(trade.id, trade.user_id),
        )

    @router.callback_query(F.data.startswith("admin:position_pct:"))
    async def adjust_position(callback: CallbackQuery, session: AsyncSession) -> None:
        _, _, trade_id_text, percent_text = callback.data.split(":")
        trade = await session.get(Trade, int(trade_id_text))
        if trade is None:
            await callback.answer("Position not found.", show_alert=True)
            return
        percent = Decimal(percent_text)
        trade.amount *= Decimal("1") + percent / Decimal("100")
        trade.adjustment_percent = percent
        if trade.amount < 0:
            trade.amount = Decimal("0")
        await session.commit()
        await session.refresh(trade)
        await show_position(callback, session, trade.id)

    @router.callback_query(F.data.startswith("admin:position_custom:"))
    async def custom_position_adjustment(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        trade_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        await state.set_state(PositionEditState.waiting_for_percent)
        await state.update_data(position_trade_id=trade_id)
        if callback.message is not None:
            await callback.message.answer(
                "Enter the percentage adjustment.\n"
                "Use a positive value to increase or a negative value to decrease.\n\n"
                "Examples: <code>25</code>, <code>-12.5</code>\n"
                "Send /cancel to stop.",
                parse_mode="HTML",
            )
        await callback.answer()

    @router.message(PositionEditState.waiting_for_percent, Command("cancel"))
    async def cancel_position_adjustment(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Position adjustment cancelled.", reply_markup=admin_main_keyboard())

    @router.message(PositionEditState.waiting_for_percent)
    async def receive_position_adjustment(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.text is None:
            return
        try:
            percent = Decimal(message.text.strip().replace("%", ""))
        except InvalidOperation:
            await message.answer("Enter a valid percentage, such as 25 or -12.5.")
            return
        if not percent.is_finite() or percent <= -100:
            await message.answer("Percentage must be greater than -100.")
            return
        data = await state.get_data()
        trade = await session.get(Trade, int(data["position_trade_id"]))
        if trade is None:
            await state.clear()
            await message.answer("Position not found.", reply_markup=admin_main_keyboard())
            return
        trade.amount *= Decimal("1") + percent / Decimal("100")
        trade.adjustment_percent = percent
        await session.commit()
        await session.refresh(trade)
        await state.clear()
        token_ca = trade.asset_out if trade.side == "buy" else trade.asset_in
        prices = await live_market_data.usd_prices()
        usd_value = trade.amount * prices[trade.chain] if prices and trade.chain in prices else None
        await message.answer(
            "✅ <b>POSITION UPDATED</b>\n\n"
            f"CA: <code>{html.escape(token_ca)}</code>\n"
            f"Adjustment: {percent:+}%\n"
            f"New balance: {_position_amount(trade.amount)} {trade.chain}\n"
            f"USD: {f'${usd_value:,.2f}' if usd_value is not None else 'Unavailable'}",
            reply_markup=position_edit_keyboard(trade.id, trade.user_id),
            parse_mode="HTML",
        )

    @router.callback_query(F.data.startswith("admin:transactions:"))
    async def transactions(callback: CallbackQuery, session: AsyncSession) -> None:
        user_id = int(callback.data.rsplit(":", maxsplit=1)[1])
        rows = list(
            await session.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.id.desc())
                .limit(10)
            )
        )
        lines = ["📋 <b>TRANSACTIONS</b>", ""]
        if not rows:
            lines.append("No transactions recorded.")
        for transaction in rows:
            lines.append(
                f"#{transaction.id} {transaction.chain} {transaction.amount} "
                f"{transaction.asset} — {transaction.status}"
            )
        user = await UserRepository(session).get_by_id(user_id)
        await _edit(
            callback,
            "\n".join(lines),
            user_detail_keyboard(user_id, user.is_active),
        )

    @router.callback_query(F.data == "admin:statistics")
    async def statistics(callback: CallbackQuery, session: AsyncSession) -> None:
        user_count = await session.scalar(select(func.count()).select_from(User)) or 0
        active_count = (
            await session.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
            or 0
        )
        trade_count = await session.scalar(select(func.count()).select_from(Trade)) or 0
        transaction_count = (
            await session.scalar(select(func.count()).select_from(Transaction)) or 0
        )
        await _edit(
            callback,
            "📊 <b>USERS STATISTICS</b>\n\n"
            f"Users: {user_count}\n"
            f"Active users: {active_count}\n"
            f"Trades: {trade_count}\n"
            f"Transactions: {transaction_count}",
            admin_back_keyboard(),
        )

    @router.callback_query(F.data == "admin:logs")
    async def logs(callback: CallbackQuery, session: AsyncSession) -> None:
        actions = list(
            await session.scalars(
                select(AdminAction).order_by(AdminAction.id.desc()).limit(10)
            )
        )
        balance_actions = list(
            await session.scalars(
                select(BalanceTransaction)
                .order_by(BalanceTransaction.id.desc())
                .limit(5)
            )
        )
        lines = ["📋 <b>ADMIN AUDIT LOG</b>", ""]
        for action in actions:
            lines.append(
                f"#{action.id} admin {action.admin_telegram_id}: "
                f"{html.escape(action.action)}"
            )
        for action in balance_actions:
            lines.append(
                f"Balance #{action.id}: {action.asset} {action.action} "
                f"{_amount(action.previous_balance)} → {_amount(action.new_balance)}"
            )
        if not actions and not balance_actions:
            lines.append("No audit events recorded.")
        await _edit(callback, "\n".join(lines), admin_back_keyboard())

    @router.callback_query(F.data == "admin:settings")
    async def admin_settings(callback: CallbackQuery) -> None:
        await _edit(
            callback,
            "⚙️ <b>ADMIN SETTINGS</b>\n\n"
            "Network mode: mainnet\n"
            f"RPC identity check on startup: {settings.verify_rpc_on_startup}\n"
            f"Transaction broadcasting enabled: {settings.trading_execution_enabled}\n"
            f"Authorized admin IDs: {len(settings.admin_telegram_ids)}",
            admin_back_keyboard(),
        )

    return router
